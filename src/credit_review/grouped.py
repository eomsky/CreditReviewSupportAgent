"""Central work queue: shared-history lookup before every bounded batch."""
import json
from concurrent.futures import ThreadPoolExecutor, wait
from time import monotonic

from .models import BatchActions, Action
from .parallel import WorkerHarness, CachedTools, Measurements
from .shared_work import SharedWork, signature
from .store import atomic_json
from .run_health import service_failure
from .registry import FACTORS

GROUPS = [('F01','F02','F03','F04','F05'), ('F06','F07','F08','F09'),
          ('F10','F11','F12'), ('F13','F14','F15','F16'), ('F17','F18','F19'),
          ('F20','F21','F22','F23'), ('F25','F26','F27','F28','F29')]


def group_context(worker, ids):
    sources, datasets, calculations, factors, related, reusable = {}, {}, {}, {}, {}, {}
    for fid in ids:
        context = worker.context(fid)
        context['available_actions'] = [a for a in context['available_actions'] if a not in ('plan', 'reframe')]
        if worker.state.factors[fid].reframes < 3 and 'search' not in context['available_actions']:
            context['available_actions'].append('search')  # requires a changed inquiry after stalled retrieval
        for source in context.pop('sources')[:2]:
            source_limit = getattr(worker, 'source_excerpt_chars', 1200)
            if not source.get('read_complete') and len(source['text']) > source_limit:
                source['text'] = source['text'][:source_limit]
                source['excerpt_only'] = True
                source['omission_note'] = 'Focused excerpt; use read/search to inspect omitted content before concluding.'
            sources[source['id']] = source
        datasets.update(context.pop('datasets'))
        calculations.update(context.pop('calculations'))
        related.update(context.pop('related_findings'))
        reusable.update(context.pop('shared_datasets'))
        factors[fid] = context
    # All members actually receive this common source payload. Register it as
    # available evidence for each member without marking any requirement fulfilled.
    shared_ids = set(sources)
    worker.retriever.read(sorted(shared_ids))
    for fid in ids:
        f = worker.state.factors[fid]
        f.evidence_ids = sorted(set(f.evidence_ids) | shared_ids)
        # Keep the complete evidence ledger in state.json; don't repeat it N times
        # in a batch prompt. All shared source IDs remain usable by all members.
        factors[fid]['state']['evidence_ids'] = [sid for sid in f.recent_source_ids if sid in sources][:2]
        factors[fid]['state']['recent_source_ids'] = factors[fid]['state']['evidence_ids']
    # Common payloads appear once; every factor retains its actual provenance IDs.
    result = {'review_date': str(worker.state.review_date), 'factors': factors,
              'sources': sources, 'datasets': datasets, 'calculations': calculations,
              'related_findings': related, 'shared_datasets': reusable}
    if len(json.dumps(result, ensure_ascii=False)) > 48000:
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
        if action.action in ('plan', 'reframe'):
            raise ValueError('Attach inquiry to search/read/dataset/calculate/reuse/conclude; no planning-only batch action')
        if action.inquiry:
            if not f.inquiry:
                worker.apply(fid, Action(action='plan', reason=action.reason, inquiry=action.inquiry), parent)
            elif action.inquiry != f.inquiry:
                worker.apply(fid, Action(action='reframe', reason=action.reason, inquiry=action.inquiry), parent)
        if action.action not in worker.context(fid)['available_actions']:
            raise ValueError('Unavailable group action')
        if on_status:
            on_status(fid, action.action, action.inquiry.question if action.inquiry else
                      (f.inquiry.question if f.inquiry else '근거·공통 자료 검토'))
        f.steps += 1
        memory = getattr(worker, 'shared_work', None)
        result = memory.reuse_exact(fid, action, parent) if memory else None
        if not result:
            result = worker.apply(fid, action, parent)
        if memory:
            memory.record(fid, action, parent, result)
        f.error = None
        f.failed_response = None
        if action.action == 'conclude' and (action.judgement.conflicts or
                (FACTORS[fid]['critical'] and (action.judgement.missing or f.coverage < 1))):
            # Reference validation alone does not settle a material disputed issue.
            worker.store.put('group_provisional_judgement', {'factor_id':fid,
                'judgement':action.judgement.model_dump()}, [parent])
            f.judgement = None
            f.status = 'GROUP_DEEP_REVIEW'
            f.error = 'Grouped review found conflicts or material evidence gaps; perform focused verification.'
        updated.append(fid)
        worker.store.event(action=action.action, factor_id=fid, grouped=True)
        # Broadcast only validated datasets and executed calculations, never predicted values.
        if action.action == 'dataset':
            aid = result
            for other in ids:
                if other != fid and not worker.state.factors[other].judgement:
                    worker.apply(other, Action(action='reuse', reason='Validated group dataset', reuse_dataset_ids=[aid]), parent)
        if action.action == 'calculate':
            aid = result
            for other in ids:
                target = worker.state.factors[other]
                if not target.judgement and aid not in target.calculation_ids:
                    target.calculation_ids.append(aid)
    return updated


def apply_group_independently(worker, ids, raw, parent, on_status=None):
    """Keep valid peer results when one action has a semantic/schema error."""
    items = json.loads(raw)['actions']
    fids = [item['factor_id'] for item in items]
    if not items or len(set(fids)) != len(fids) or not set(fids).issubset(ids):
        raise ValueError('Unexpected or duplicate factor in group response')
    # Shared source/data/calculation dependencies are applied before conclusions.
    order = {'plan':0, 'reframe':0, 'search':1, 'read':1, 'reuse':2, 'dataset':2, 'calculate':3, 'conclude':4}
    items.sort(key=lambda item: order.get(item.get('action', {}).get('action'), 9))
    for item in items:
        fid = item['factor_id']
        try:
            apply_group_reply(worker, ids, json.dumps({'actions':[item]}), parent, on_status)
        except ValueError as error:
            f = worker.state.factors[fid]
            f.error = str(error)[:1500]
            f.failed_response = json.dumps(item['action'])[:2000]
            worker.store.event(action='group_item_repair', factor_id=fid, error=f.error)


class ReviewStopped(RuntimeError):
    pass


def shared_context(worker, ids, memory):
    """Search prior work without an LLM; expose candidates with provenance labels."""
    memory.refresh()
    matches = {}
    for fid in ids:
        f = worker.state.factors[fid]
        query = FACTORS[fid]['name'] + ' ' + ' '.join(FACTORS[fid]['required_evidence'])
        if f.inquiry:
            query += ' ' + f.inquiry.question
        found = memory.search(query, limit=3)
        matches[fid] = [{**hit, 'summary':hit.get('summary','')[:400]} for hit in found]
        # Make relevant validated assets available, not assertions of applicability.
        for hit in found:
            aid = hit.get('artifact_id')
            if hit.get('kind') == 'dataset':
                worker.apply(fid, Action(action='reuse', reason='Shared history candidate; verify scope before use',
                    reuse_dataset_ids=[aid]), 'shared_history')
            elif hit.get('kind') == 'calculation' and hit['verification'] == 'EXECUTED':
                payload = worker.store.get(aid)['payload']
                worker.apply(fid, Action(action='reuse', reason='Shared calculation inputs',
                    reuse_dataset_ids=payload['plan']['dataset_ids']), 'shared_history')
                if aid not in f.calculation_ids:
                    f.calculation_ids.append(aid)
            # Lookup results are candidate sources, never automatically fulfilled evidence.
            if hit.get('evidence_ids'):
                rows = worker.retriever.read(hit['evidence_ids'])
                f.evidence_ids = sorted(set(f.evidence_ids) | {r['id'] for r in rows})
                # Prior-work candidates stay in prior_work/evidence_ids. Do not
                # replace this factor's ranked source window with another topic.
        worker.store.event(action='shared_history_search', factor_id=fid, hits=len(found))
    context = group_context(worker, ids)
    context['prior_work'] = matches
    context['reuse_policy'] = ('Search completed prior_work before requesting more work. '
        'Check entity, period, scope, units, assumptions. Prior LLM text is not verified truth. '
        'Only request unmet needs. Emit one shared tool request for duplicate needs across factors.')
    if len(json.dumps(context, ensure_ascii=False)) > getattr(worker, 'context_char_budget', 24000):
        raise ValueError('Group context too large')
    return context


def analyse_grouped_serial(h, targets, concurrency=1, metrics=None, rounds=6, time_budget=60, batch_size=6):
    """One shared state, bounded batches for ALL follow-ups, no individual fallback.

    A single outstanding LLM batch intentionally coalesces all ready requests and
    removes stale snapshot races. Tools retain run-local single-flight caching.
    """
    metrics = metrics or Measurements()
    deadline = metrics.started + time_budget
    if hasattr(h.client, 'set_deadline'):
        h.client.set_deadline(deadline)
    tools = CachedTools(h.retriever, h.executor, metrics)
    worker = WorkerHarness(h.store, h.state, tools, h.client, tools)
    memory = worker.shared_work = SharedWork(worker)
    pending = [fid for fid in targets if not h.state.factors[fid].judgement]
    attempted, repeated, rechecked = {}, {}, set()
    consecutive_failures = 0
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='credit-batch')
    future = None

    def progress():
        # Planning alone is not evidence of useful progress.
        return tuple((fid, tuple(f.evidence_ids), tuple(f.read_source_ids), tuple(f.dataset_ids), tuple(f.calculation_ids),
            f.judgement.model_dump_json() if f.judgement else None)
            for fid, f in h.state.factors.items() if fid in targets)

    def event(kind, fid=None, value=None, active=()):
        return {'kind':kind, 'factor_id':fid, 'value':value, 'active':list(active),
            'finished':sum(bool(h.state.factors[f].judgement) for f in targets),
            'total':len(targets), 'metrics':metrics.snapshot()}

    try:
        stale_rounds = 0
        for turn in range(rounds):
            if not pending:
                return
            before = progress()
            # One bounded continuation after retrieval makes newly obtained
            # evidence useful before routing every remaining factor.
            waiting = list(pending)
            while waiting:
                if monotonic() >= deadline:
                    raise ReviewStopped('실행시간 한도에 도달하여 중단했습니다. 확보한 결과는 보존했습니다.')
                ready = [fid for fid in waiting if fid not in ('F24', 'F30') or
                    all(dep in attempted or h.state.factors[dep].judgement for dep in
                        ([f'F{i:02}' for i in range(13,24)] if fid == 'F24' else targets)
                        if dep in targets and dep != fid)]
                if not ready:
                    ready = waiting[:1]
                ids = ready[:max(1, min(6, batch_size))]
                for fid in ids:
                    worker.prepare_evidence(fid)
                while ids:
                    try:
                        context = shared_context(worker, ids, memory)
                        break
                    except ValueError as error:
                        if len(ids) == 1:
                            raise ReviewStopped('공통 근거가 입력 한도를 초과했습니다. 결과를 보존하고 중단했습니다.') from error
                        ids = ids[:-1]
                for fid in ids:
                    waiting.remove(fid)
                    attempted[fid] = attempted.get(fid, 0) + 1
                parent = h.store.put('group_input', context)
                for fid in ids:
                    yield event('status', fid, {'action':'review',
                        'question':'다른 파트의 기존 결과 확인 후 부족한 판단을 함께 검토'}, ids)
                future = pool.submit(worker.client.next_actions, context)
                continue_ids = []
                while not future.done():
                    # A bounded wait keeps UI heartbeats alive during slow inference.
                    wait([future], timeout=min(0.5, max(0.001, deadline-monotonic())))
                    if monotonic() >= deadline:
                        raise ReviewStopped('LLM 응답 대기시간 한도로 중단했습니다. 확보한 결과는 보존했습니다.')
                    yield event('heartbeat', active=ids)
                try:
                    raw = future.result()
                    response = h.store.put('group_output', {'raw':raw}, [parent])
                    items = json.loads(raw)['actions']
                    reply_ids = [item['factor_id'] for item in items]
                    if not items or len(set(reply_ids)) != len(reply_ids) or not set(reply_ids).issubset(ids):
                        raise ValueError('Unexpected or duplicate factor in group response')
                    # Block identical requests by the same factor; different factors reuse results.
                    retained = []
                    for item in items:
                        fid = item['factor_id']
                        try:
                            action = Action.model_validate(item['action'])
                        except ValueError:
                            retained.append(item)
                            continue
                        key = (fid, signature(action))
                        repeated[key] = repeated.get(key, 0) + 1
                        if repeated[key] > 2:
                            raise ReviewStopped('새로운 근거 없이 동일 요청이 반복되어 조기 중단했습니다.')
                        retained.append(item)
                    apply_group_independently(worker, ids, json.dumps({'actions':retained}), response)
                    continue_ids = [item['factor_id'] for item in retained
                        if item.get('action', {}).get('action') in ('search', 'read')
                        and not h.state.factors[item['factor_id']].error
                        and attempted[item['factor_id']] == 1]
                    consecutive_failures = 0
                    for fid in ids:
                        f = h.state.factors[fid]
                        if f.status == 'GROUP_DEEP_REVIEW':
                            if fid in rechecked:
                                # Keep the qualified finding after one explicit recheck.
                                provisional = next(a for a in reversed(h.store.artifacts())
                                    if a['stage']=='group_provisional_judgement' and a['payload']['factor_id']==fid)
                                from .models import Judgement
                                f.judgement = Judgement.model_validate(provisional['payload']['judgement'])
                                f.status = 'CONFLICT' if f.judgement.conflicts else 'PARTIALLY_FULFILLED'
                            else:
                                rechecked.add(fid)
                except ReviewStopped:
                    raise
                except Exception as error:
                    h.store.event(action='batch_repair', factors=ids, error=str(error))
                    if service_failure(error):
                        raise
                    consecutive_failures += 1
                    if consecutive_failures >= 2:
                        raise ReviewStopped('연속 두 번 LLM 요청이 실패하여 조기 중단했습니다. 오류 기록과 기존 결과를 보존했습니다.') from error
                    if 'context' in str(error).lower():
                        # Retry once with materially smaller input, not an unchanged prompt.
                        worker.context_char_budget = 12000
                        worker.source_excerpt_chars = 600
                    for fid in ids:
                        h.state.factors[fid].error = str(error)[:1000]
                h.state.report_id = None
                h.save()
                for fid in ids:
                    f = h.state.factors[fid]
                    if f.judgement and metrics.first_report_seconds is None:
                        metrics.first_report_seconds = monotonic()-metrics.started
                    yield event('state', fid, f.model_copy(deep=True), ids)
                    yield event('done', fid, active=[other for other in ids if other != fid])
                atomic_json(h.store.path/'performance.json', metrics.snapshot())
                waiting = continue_ids + waiting
            pending = [fid for fid in pending if not h.state.factors[fid].judgement]
            stale_rounds = stale_rounds + 1 if progress() == before else 0
            if pending and stale_rounds >= 2:
                raise ReviewStopped('두 회차 동안 새 근거나 분석 결과가 늘지 않아 조기 중단했습니다.')
        if pending:
            raise ReviewStopped('후속 요청 회차 한도에 도달했습니다. 확보한 결과는 보존했습니다.')
    finally:
        # Production client has the same deadline. Do not block the UI joining an expired call.
        pool.shutdown(wait=False, cancel_futures=True)
        h.save()
        atomic_json(h.store.path/'performance.json', metrics.snapshot())


def analyse_grouped(h, targets, concurrency=1, metrics=None, rounds=6, time_budget=60, batch_size=6):
    if concurrency <= 1:
        yield from analyse_grouped_serial(h, targets, metrics=metrics, rounds=rounds,
                                         time_budget=time_budget, batch_size=batch_size)
    else:
        from .queued import analyse_queued
        yield from analyse_queued(h, targets, metrics=metrics, rounds=rounds,
                                  time_budget=time_budget, batch_size=batch_size, concurrency=concurrency)
