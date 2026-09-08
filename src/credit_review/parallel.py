"""Bounded factor scheduling. Only the consumer writes the review state."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from queue import Queue, Empty
from threading import Event, Lock, get_ident
from time import monotonic
import hashlib

from .harness import Harness
from .registry import FACTORS
from .run_health import service_failure
from .store import atomic_json, json_text


@contextmanager
def run_lease(h):
    path = h.store.path / '.run.lock'
    try:
        with path.open('x') as out:
            out.write('Active report writer')
    except FileExistsError:
        raise RuntimeError('This report already has an active writer')
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


class Measurements:
    def __init__(self):
        self.started = monotonic()
        self.lock = Lock()
        self.records = []
        self.inflight = {}
        self.sequence = 0
        self.thread_calls = {}
        self.usage = []
        self.first_report_seconds = None

    def record(self, kind, started, cached=False, call_id=None):
        with self.lock:
            ended = monotonic()
            self.records.append({'kind': kind, 'seconds': ended-started, 'cached': cached,
                'started_seconds':started-self.started, 'ended_seconds':ended-self.started,
                **({'call_id':call_id} if call_id is not None else {})})

    def begin(self, kind):
        with self.lock:
            self.sequence += 1
            self.inflight[self.sequence] = (kind, monotonic())
            self.thread_calls[get_ident()] = self.sequence
            return self.sequence

    def finish(self, token):
        with self.lock:
            kind, started = self.inflight.pop(token)
            if self.thread_calls.get(get_ident())==token:
                self.thread_calls.pop(get_ident())
        self.record(kind, started,call_id=token)

    def record_usage(self, usage):
        with self.lock:
            token=self.thread_calls.get(get_ident())
            current=self.inflight.get(token)
            self.usage.append({**{k:usage.get(k) for k in
                ('prompt_tokens','completion_tokens','total_tokens')},
                'call_id':token,'kind':current[0] if current else None,
                'reasoning_tokens':(usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),
                'received_seconds':monotonic()-self.started})

    def snapshot(self):
        with self.lock:
            elapsed = monotonic()-self.started
            intervals = [(r['started_seconds'],r['ended_seconds']) for r in self.records
                         if r['kind'].startswith('llm_')]
            intervals += [(started-self.started, elapsed) for kind, started in self.inflight.values()
                          if kind.startswith('llm_')]
            busy, right = 0.0, 0.0
            merged = []
            for start, end in sorted(intervals):
                busy += max(0, end-max(right,start))
                right = max(right,end)
                if merged and start <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], end)
                else:
                    merged.append([start, end])
            local_overlap = sum(max(0, min(r['ended_seconds'], end)-max(r['started_seconds'], start))
                for r in self.records if r['kind']=='local_apply' for start, end in merged)
            return {'elapsed_seconds': elapsed,
                    'first_report_seconds': self.first_report_seconds,
                    'llm_calls': sum(r['kind'].startswith('llm_') for r in self.records),
                    'cache_hits': sum(r['cached'] for r in self.records),
                    'llm_inflight':len(self.inflight),
                    'request_busy_fraction':busy/elapsed if elapsed else 0,
                    'mean_requests_inflight':sum(end-start for start,end in intervals)/elapsed if elapsed else 0,
                    'request_gap_seconds':max(0,elapsed-busy),
                    'local_apply_during_request_seconds':local_overlap,
                    'utilization_note':'Client HTTP occupancy, including server queue/network; not GPU utilization',
                    'token_usage':list(self.usage),
                    'operations': list(self.records)}


class MeasuredClient:
    def __init__(self, client, metrics):
        self.client, self.metrics = client, metrics
        if hasattr(client, 'set_usage_observer'):
            client.set_usage_observer(metrics.record_usage)

    def _call(self, method, context):
        token = self.metrics.begin('llm_'+method)
        try:
            return getattr(self.client, method)(context)
        finally:
            self.metrics.finish(token)

    def set_deadline(self, deadline):
        if hasattr(self.client, 'set_deadline'):
            self.client.set_deadline(deadline)

    def next_action(self, context):
        return self._call('next_action', context)

    def synthesize(self, context):
        return self._call('synthesize', context)

    def next_actions(self, context):
        return self._call('next_actions', context)

    def prepare_financial(self, context):
        return self._call('prepare_financial', context)

    def review_bundle(self, context):
        return self._call('review_bundle', context)

    def stream_report(self, context):
        token=self.metrics.begin('llm_stream_report')
        try:
            yield from self.client.stream_report(context)
        finally:
            self.metrics.finish(token)


class CachedTools:
    """Run-scoped exact-input cache. Serialises only search/index access, not LLM."""
    def __init__(self, retriever, executor, metrics):
        self.retriever, self.executor, self.metrics = retriever, executor, metrics
        self.lock = Lock()
        self.cache = {}
        self.operation_locks = {}
        self.mode = retriever.mode

    def _cached(self, kind, key, call):
        started = monotonic()
        # Single-flight per key; unrelated calculations do not block retrieval.
        with self.lock:
            operation_lock = self.operation_locks.setdefault((kind, key), Lock())
        with operation_lock:
            hit = (kind, key) in self.cache
            if not hit:
                self.cache[kind, key] = call()
            value = deepcopy(self.cache[kind, key])
        self.metrics.record(kind, started, hit)
        return value

    def search(self, query, limit=6):
        return self._cached('search', (query, limit), lambda: self.retriever.search(query, limit))

    def read(self, ids):
        return self._cached('read', tuple(ids), lambda: self.retriever.read(ids))

    def execute(self, plan, datasets):
        key = hashlib.sha256(json_text({'plan': plan.model_dump(), 'datasets': datasets}).encode()).hexdigest()
        return self._cached('calculate', key, lambda: self.executor.execute(plan, datasets))


class WorkerHarness(Harness):
    def save(self):
        # A worker owns a snapshot, never the shared state.json.
        pass


def analyse_factors(h, targets, concurrency=2, metrics=None):
    """Yield activity/progress events on the caller thread; join workers on exit."""
    metrics = metrics or Measurements()
    concurrency = max(1, min(2, concurrency))
    tools = CachedTools(h.retriever, h.executor, metrics)
    queue, stop = Queue(), Event()
    pending = [fid for fid in targets if not h.state.factors[fid].judgement]
    finished = set(targets) - set(pending)
    active = {}
    failure = None
    # Bootstrap identity once. Downstream repayment and overall risk need prior findings.
    dependencies = {fid: ({'F01'} & set(targets)) for fid in targets if fid != 'F01'}
    dependencies['F24'] = {f'F{i:02}' for i in range(13,24)} & set(targets)
    dependencies['F30'] = set(targets) - {'F30'}

    def work(fid, snapshot):
        worker = WorkerHarness(h.store, snapshot, tools, h.client, tools)
        worker.lock_name = f'.step-{fid}.lock'
        try:
            if worker.state.factors[fid].status in ('ERROR', 'LIMIT_REACHED', 'NO_PROGRESS'):
                worker.reset_factor(fid)
            worker.prepare_evidence(fid)
            for _ in range(24):
                if stop.is_set():
                    break
                f = worker.state.factors[fid]
                question = f.inquiry.question if f.inquiry else FACTORS[fid]['name']+'의 여신 위험과 완화요인 검토'
                queue.put(('status', fid, {'action': 'review', 'question': question}))
                def status(action, question):
                    queue.put(('status', fid, {'action': action, 'question': question}))
                f = worker.step(fid, max_steps=24, repair_attempts=2, on_status=status)
                queue.put(('state', fid, f.model_copy(deep=True)))
                if f.error and service_failure(f.error):
                    stop.set()
                    queue.put(('failure', fid, f.error))
                    break
                if f.judgement or f.status in ('ERROR', 'LIMIT_REACHED', 'NO_PROGRESS'):
                    break
        except Exception as error:
            stop.set()
            queue.put(('failure', fid, str(error)))
        finally:
            queue.put(('done', fid, None))

    pool = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix='credit-factor')
    try:
        while pending or active:
            if not stop.is_set():
                for fid in list(pending):
                    if len(active) >= concurrency:
                        break
                    if not dependencies.get(fid, set()).issubset(finished):
                        continue
                    pending.remove(fid)
                    active[fid] = pool.submit(work, fid, h.state.model_copy(deep=True))
            if not active:
                break
            try:
                kind, fid, value = queue.get(timeout=0.5)
            except Empty:
                yield {'kind': 'heartbeat', 'active': list(active), 'metrics': metrics.snapshot()}
                continue
            if kind == 'state':
                h.state.factors[fid] = value
                h.state.report_id = None
                h.save()
                if value.judgement and metrics.first_report_seconds is None:
                    metrics.first_report_seconds = monotonic()-metrics.started
            elif kind == 'failure':
                failure = value
            elif kind == 'done':
                active.pop(fid).result()
                finished.add(fid)
            atomic_json(h.store.path/'performance.json', metrics.snapshot())
            yield {'kind': kind, 'factor_id': fid, 'value': value, 'active': list(active),
                   'finished': len(finished), 'total': len(targets), 'metrics': metrics.snapshot()}
        if failure:
            raise RuntimeError(failure)
    finally:
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
        # Preserve in-flight completed steps even when the UI consumer exits early.
        while not queue.empty():
            kind, fid, value = queue.get()
            if kind == 'state':
                h.state.factors[fid] = value
                h.state.report_id = None
                h.save()
        atomic_json(h.store.path/'performance.json', metrics.snapshot())
