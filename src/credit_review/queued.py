"""Bounded, completion-driven LLM queue; only the coordinator mutates state."""
import json
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from time import monotonic

from .parallel import Measurements, CachedTools, WorkerHarness
from .shared_work import SharedWork, signature
from .models import Action, Judgement
from .store import atomic_json
from .run_health import service_failure


FINANCIAL = {f'F{i:02}' for i in range(12,25)}
TERMINAL = {'NO_PROGRESS', 'LIMIT_REACHED'}


def eligible(fid, active, states, targets):
    if fid in active:
        return False
    # Prevent duplicate financial extraction/calculation before shared assets land.
    if fid in FINANCIAL and active & FINANCIAL:
        return False
    deps = ({f'F{i:02}' for i in range(13,24)} if fid == 'F24'
            else set(targets)-{'F30'} if fid == 'F30' else set()) & set(targets)
    return all(states[d].judgement is not None or states[d].status in TERMINAL for d in deps)


def analyse_queued(h, targets, metrics=None, rounds=6, time_budget=60, batch_size=6, concurrency=2):
    # Resolve after Streamlit reloads rather than retaining obsolete class objects.
    from .grouped import shared_context, apply_group_independently, ReviewStopped
    metrics = metrics or Measurements()
    deadline = metrics.started + time_budget
    if hasattr(h.client, 'set_deadline'):
        h.client.set_deadline(deadline)
    tools = CachedTools(h.retriever, h.executor, metrics)
    worker = WorkerHarness(h.store, h.state, tools, h.client, tools)
    memory = worker.shared_work = SharedWork(worker)
    waiting = [fid for fid in targets if not h.state.factors[fid].judgement]
    attempts, repeats, stalls, rechecked = {}, {}, {}, set()
    jobs = {}
    failures = 0
    slots = max(1,min(2,concurrency))
    pool = ThreadPoolExecutor(max_workers=slots, thread_name_prefix='credit-ready')

    def active_ids():
        return {fid for job in jobs.values() for fid in job['ids']}

    def stamp(fid):
        f = h.state.factors[fid]
        return (tuple(f.evidence_ids), tuple(f.read_source_ids), tuple(f.dataset_ids),
                tuple(f.calculation_ids), f.judgement.model_dump_json() if f.judgement else None)

    def event(kind, fid=None, value=None):
        return {'kind':kind,'factor_id':fid,'value':value,'active':sorted(active_ids()),
                'finished':sum(bool(h.state.factors[f].judgement) for f in targets),
                'total':len(targets),'metrics':metrics.snapshot()}

    try:
        while waiting or jobs:
            if monotonic() >= deadline:
                raise ReviewStopped('실행시간 한도에 도달하여 대기열을 중단했습니다. 확보한 결과는 보존했습니다.')
            # Fill at most two service slots. Inputs are rebuilt from current shared
            # results at dispatch, never cached while dependency results are pending.
            while len(jobs) < slots and waiting:
                if any(future.done() for future in jobs):
                    break  # consume ready errors/results before sending more work
                active = active_ids()
                ready = [fid for fid in waiting if eligible(fid,active,h.state.factors,targets)]
                if not ready:
                    break
                ids = ready[:max(1,min(6,batch_size))]
                for fid in ids:
                    worker.prepare_evidence(fid)
                while ids:
                    try:
                        context = shared_context(worker,ids,memory)
                        break
                    except ValueError as error:
                        if len(ids)==1:
                            raise ReviewStopped('공통 근거가 입력 한도를 초과했습니다.') from error
                        ids = ids[:-1]
                if any(future.done() for future in jobs):
                    break
                for fid in ids:
                    waiting.remove(fid)
                    attempts[fid] = attempts.get(fid,0)+1
                parent = h.store.put('group_input',context)
                job = {'ids':ids,'parent':parent,'before':{fid:stamp(fid) for fid in ids}}
                future = pool.submit(worker.client.next_actions,context)
                jobs[future] = job
                h.store.event(action='queue_dispatch',factors=ids,active_requests=len(jobs),
                              waiting_factors=len(waiting),input_id=parent)
                for fid in ids:
                    yield event('status',fid,{'action':'review',
                        'question':'준비된 근거를 분석 중 · 독립적인 다음 묶음도 함께 처리'})
                atomic_json(h.store.path/'performance.json',metrics.snapshot())
            if not jobs:
                raise ReviewStopped('선행 분석이 준비되지 않아 후속 요청을 중단했습니다.')
            completed, _ = wait(jobs,timeout=min(.5,max(.001,deadline-monotonic())),return_when=FIRST_COMPLETED)
            if not completed:
                yield event('heartbeat')
                continue
            if monotonic() >= deadline:
                raise ReviewStopped('LLM 응답 대기시간 한도로 중단했습니다. 확보한 결과는 보존했습니다.')
            for future in completed:
                job = jobs.pop(future)
                ids = job['ids']
                try:
                    raw = future.result()
                    response = h.store.put('group_output',{'raw':raw},[job['parent']])
                    items = json.loads(raw)['actions']
                    fids = [item['factor_id'] for item in items]
                    if not items or len(set(fids))!=len(fids) or not set(fids).issubset(ids):
                        raise ValueError('Unexpected or duplicate factor in group response')
                    retained = []
                    for item in items:
                        try:
                            action = Action.model_validate(item['action'])
                        except ValueError:
                            retained.append(item)
                            continue  # independent validator retains the good peers
                        key = (item['factor_id'],signature(action))
                        repeats[key] = repeats.get(key,0)+1
                        if repeats[key]>2:
                            f = h.state.factors[item['factor_id']]
                            f.status, f.error = 'NO_PROGRESS', 'Identical requests repeated; factor stopped, independent work continues.'
                            h.store.event(action='factor_stopped', factor_id=item['factor_id'], error=f.error)
                            continue
                        retained.append(item)
                    local_started = monotonic()
                    try:
                        # Other submitted HTTP calls keep running while local
                        # retrieval, validation and Python calculations execute.
                        if retained:
                            apply_group_independently(worker,ids,json.dumps({'actions':retained}),response)
                    finally:
                        metrics.record('local_apply', local_started)
                    failures = 0
                    for fid in ids:
                        f = h.state.factors[fid]
                        if f.status == 'GROUP_DEEP_REVIEW':
                            if fid in rechecked:
                                provisional = next(a for a in reversed(h.store.artifacts())
                                    if a['stage']=='group_provisional_judgement' and a['payload']['factor_id']==fid)
                                f.judgement = Judgement.model_validate(provisional['payload']['judgement'])
                                f.status = 'CONFLICT' if f.judgement.conflicts else 'PARTIALLY_FULFILLED'
                            else:
                                rechecked.add(fid)
                        stalls[fid] = stalls.get(fid,0)+1 if stamp(fid)==job['before'][fid] else 0
                        if not f.judgement and stalls[fid]>=2:
                            f.status = 'NO_PROGRESS'
                            f.error = f.error or 'No new evidence or result after two follow-ups.'
                            h.store.event(action='factor_stopped', factor_id=fid, error=f.error)
                except ReviewStopped:
                    raise
                except Exception as error:
                    h.store.event(action='batch_repair',factors=ids,error=str(error))
                    if service_failure(error):
                        raise
                    failures += 1
                    if failures>=2:
                        raise ReviewStopped('연속 두 번 LLM 요청이 실패하여 조기 중단했습니다.') from error
                    if 'context' in str(error).lower():
                        worker.context_char_budget=12000
                        worker.source_excerpt_chars=600
                    for fid in ids:
                        h.state.factors[fid].error=str(error)[:1000]
                h.state.report_id=None
                h.save()
                again=[]
                for fid in ids:
                    f=h.state.factors[fid]
                    if f.judgement:
                        if metrics.first_report_seconds is None:
                            metrics.first_report_seconds=monotonic()-metrics.started
                    elif f.status not in TERMINAL:
                        if attempts[fid]>=rounds:
                            f.status, f.error = 'LIMIT_REACHED', 'Factor follow-up limit reached.'
                        else:
                            again.append(fid)
                    yield event('state',fid,f.model_copy(deep=True))
                    yield event('done',fid)
                # Give newly ready results a short continuation, then age them
                # behind untouched work to avoid one factor monopolizing service.
                waiting = ([f for f in again if attempts[f]<2] + waiting
                           + [f for f in again if attempts[f]>=2])
                atomic_json(h.store.path/'performance.json',metrics.snapshot())
    finally:
        for future in jobs:
            future.cancel()
        pool.shutdown(wait=False,cancel_futures=True)
        h.save()
        atomic_json(h.store.path/'performance.json',metrics.snapshot())
