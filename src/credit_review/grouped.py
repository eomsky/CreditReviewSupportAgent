"""Bounded shared-evidence rounds, followed by adaptive review of unresolved factors."""
import json
from concurrent.futures import ThreadPoolExecutor
from queue import Queue, Empty
from threading import Event
from time import monotonic

from .models import BatchActions, Action
from .parallel import WorkerHarness, CachedTools, Measurements, analyse_factors
from .store import atomic_json
from .run_health import service_failure

GROUPS = [('F01','F02','F03','F04','F05'), ('F06','F07','F08','F09'),
          ('F10','F11','F12'), ('F13','F14','F15','F16'), ('F17','F18','F19'),
          ('F20','F21','F22','F23'), ('F25','F26','F27','F28','F29')]


def group_context(worker, ids):
    sources, datasets, calculations, factors, related, reusable = {}, {}, {}, {}, {}, {}
    for fid in ids:
        context = worker.context(fid)
        for source in context.pop('sources'):
            sources[source['id']] = source
        datasets.update(context.pop('datasets'))
        calculations.update(context.pop('calculations'))
        related.update(context.pop('related_findings'))
        reusable.update(context.pop('shared_datasets'))
        factors[fid] = context
    # Common payloads appear once; every factor retains its actual provenance IDs.
    result = {'review_date': str(worker.state.review_date), 'factors': factors,
              'sources': sources, 'datasets': datasets, 'calculations': calculations,
              'related_findings': related, 'shared_datasets': reusable}
    if len(json.dumps(result, ensure_ascii=False)) > 110000:
        raise ValueError('Group context too large; use focused adaptive review')
    return result


def apply_group_reply(worker, ids, raw, parent, on_status=None):
    reply = BatchActions.model_validate_json(raw)
    seen = set()
    for item in reply.actions:
        if item.factor_id not in ids or item.factor_id in seen:
            raise ValueError('Unexpected or duplicate factor in group response')
        seen.add(item.factor_id)
    updated = []
    for item in reply.actions:
        fid, action = item.factor_id, item.action
        f = worker.state.factors[fid]
        if action.action not in worker.context(fid)['available_actions']:
            raise ValueError('Unavailable group action')
        if on_status:
            on_status(fid, action.action, action.inquiry.question if action.inquiry else
                      (f.inquiry.question if f.inquiry else '근거·공통 자료 검토'))
        if action.inquiry and not f.inquiry and action.action != 'plan':
            worker.apply(fid, Action(action='plan', reason=action.reason, inquiry=action.inquiry), parent)
        f.steps += 1
        worker.apply(fid, action, parent)
        f.error = None
        f.failed_response = None
        updated.append(fid)
        worker.store.event(action=action.action, factor_id=fid, grouped=True)
        # Broadcast only validated datasets and executed calculations, never predicted values.
        if action.action == 'dataset':
            aid = f.dataset_ids[-1]
            for other in ids:
                if other != fid and not worker.state.factors[other].judgement:
                    worker.apply(other, Action(action='reuse', reason='Validated group dataset', reuse_dataset_ids=[aid]), parent)
        if action.action == 'calculate':
            aid = f.calculation_ids[-1]
            for other in ids:
                target = worker.state.factors[other]
                if not target.judgement and aid not in target.calculation_ids:
                    target.calculation_ids.append(aid)
    return updated


def analyse_grouped(h, targets, concurrency=2, metrics=None, rounds=4):
    metrics = metrics or Measurements()
    tools = CachedTools(h.retriever, h.executor, metrics)
    queue, stop = Queue(), Event()
    groups = [tuple(fid for fid in group if fid in targets and not h.state.factors[fid].judgement) for group in GROUPS]
    groups = [group for group in groups if group]
    active = set()

    def work(ids, snapshot):
        worker = WorkerHarness(h.store, snapshot, tools, h.client, tools)
        try:
            for fid in ids:
                worker.prepare_evidence(fid)
            for _ in range(rounds):
                pending = [fid for fid in ids if not worker.state.factors[fid].judgement]
                if not pending or stop.is_set():
                    break
                for fid in pending:
                    queue.put(('status', fid, {'action': 'review', 'question': '공통 원문·자료를 활용한 요인 분석'}))
                pending = pending[:3]
                context = group_context(worker, pending)
                request = worker.store.put('group_input', context)
                raw = worker.client.next_actions(context)
                response = worker.store.put('group_output', {'raw': raw}, [request])
                apply_group_reply(worker, pending, raw, response,
                    lambda fid, action, question: queue.put(('status', fid, {'action':action, 'question':question})))
                for fid in ids:
                    queue.put(('state', fid, worker.state.factors[fid].model_copy(deep=True)))
        except Exception as error:
            worker.store.event(action='group_fallback', factors=list(ids), error=str(error))
            if service_failure(error):
                stop.set()
                queue.put(('failure', ids[0], str(error)))
        finally:
            for fid in ids:
                queue.put(('state', fid, worker.state.factors[fid].model_copy(deep=True)))
                queue.put(('done', fid, None))

    failure = None
    pool = ThreadPoolExecutor(max_workers=max(1, min(2, concurrency)), thread_name_prefix='credit-group')
    futures = []
    try:
        waiting = list(groups)
        running = {}
        while waiting or running:
            while waiting and len(running) < max(1, min(2, concurrency)) and not stop.is_set():
                group = waiting.pop(0)
                future = pool.submit(work, group, h.state.model_copy(deep=True))
                futures.append(future)
                running[group] = set(group)
                active.update(group)
            if not running:
                break
            try:
                kind, fid, value = queue.get(timeout=0.5)
            except Empty:
                yield {'kind':'heartbeat', 'active':list(active), 'metrics':metrics.snapshot()}
                continue
            if kind == 'state':
                h.state.factors[fid] = value
                h.state.report_id = None
                h.save()
                if value.judgement and metrics.first_report_seconds is None:
                    metrics.first_report_seconds = monotonic()-metrics.started
            elif kind == 'done':
                active.discard(fid)
                for group in list(running):
                    running[group].discard(fid)
                    if not running[group]:
                        del running[group]
            elif kind == 'failure':
                failure = value
            atomic_json(h.store.path/'performance.json', metrics.snapshot())
            yield {'kind':kind, 'factor_id':fid, 'value':value, 'active':list(active),
                   'finished':sum(bool(h.state.factors[f].judgement) for f in targets),
                   'total':len(targets), 'metrics':metrics.snapshot()}
        if failure:
            raise RuntimeError(failure)
    finally:
        stop.set()
        pool.shutdown(wait=True, cancel_futures=True)
        while not queue.empty():
            kind, fid, value = queue.get()
            if kind == 'state':
                h.state.factors[fid] = value
                h.state.report_id = None
        h.save()
        atomic_json(h.store.path/'performance.json', metrics.snapshot())
    # F24/F30 and unresolved/conflicting work retain the original adaptive machinery.
    yield from analyse_factors(h, targets, concurrency=concurrency, metrics=metrics)
