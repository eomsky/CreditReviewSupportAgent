import json
import time

import pytest

from credit_review.grouped import analyse_grouped, apply_group_reply, shared_context, ReviewStopped
from credit_review.models import Action
from credit_review.shared_work import SharedWork
from credit_review.parallel import MeasuredClient, Measurements
from test_harness import make


def conclusion(fid):
    return {'factor_id':fid, 'action':{'action':'conclude','reason':'qualified',
        'judgement':{'summary':'원문 범위에 한정한 검토', 'evidence_ids':[], 'missing':['범위 제한']}}}


def test_six_followups_are_one_call_and_duplicate_search_is_reused(tmp_path):
    h = make(tmp_path)
    contexts = []
    ids = ['F01','F02','F04','F05','F06','F07']
    class Client:
        def next_actions(self, context):
            contexts.append(context)
            if len(contexts) == 1:
                return json.dumps({'actions':[{'factor_id':fid, 'action':{
                    'action':'search','reason':'공통 근거', 'query':'현금 cash'}} for fid in context['factors']]})
            return json.dumps({'actions':[conclusion(fid) for fid in context['factors']]})
        def next_action(self, context):
            raise AssertionError('Individual follow-up is forbidden')
    metrics = Measurements()
    h.client = MeasuredClient(Client(), metrics)
    list(analyse_grouped(h, ids, metrics=metrics))
    assert len(contexts) == 2
    assert set(contexts[1]['factors']) == set(ids)
    assert all(h.state.factors[f].judgement for f in ids)
    events = [json.loads(s) for s in (h.store.path/'events.jsonl').read_text().splitlines()]
    assert sum(e['action']=='shared_exact_reuse' for e in events) == 5
    assert sum(e['action']=='shared_history_search' for e in events) == 12
    assert metrics.snapshot()['llm_calls'] == 2  # 12 in a one-factor-per-call design


def test_prior_other_factor_calculation_is_available_before_followup(tmp_path):
    h = make(tmp_path)
    for _ in range(3):
        h.step('F24')
    calc = h.state.factors['F24'].calculation_ids[0]
    memory = SharedWork(h)
    # Target the same question in another part; no new LLM or Python call required.
    from credit_review.models import Inquiry
    h.state.factors['F17'].inquiry = Inquiry(question='historical_cf_to_maturity cash_after_maturity',
        hypotheses=['cash'], evidence_tests=['cash'], change_reason='lookup')
    ctx = shared_context(h, ['F17'], memory)
    assert calc in ctx['calculations']
    assert any(r.get('artifact_id')==calc for r in ctx['prior_work']['F17'])
    assert not h.state.factors['F17'].judgement
    assert not h.state.factors['F17'].requirements_met


def test_exact_calculation_dedup_preserves_different_assumptions(tmp_path):
    h = make(tmp_path)
    for _ in range(2):
        h.step('F24')
    aid = h.state.factors['F24'].dataset_ids[0]
    ids = ['F13','F14']
    for fid in ids:
        h.apply(fid, Action(action='reuse', reason='same data', reuse_dataset_ids=[aid]), 'test')
    h.shared_work = SharedWork(h)
    calls = []
    execute = h.executor.execute
    h.executor.execute = lambda plan, data: (calls.append(plan), execute(plan,data))[1]
    def run(fid, assumption):
        apply_group_reply(h, ids, json.dumps({'actions':[{'factor_id':fid,'action':{
            'action':'calculate','reason':'same code','calculation':{'purpose':fid,
            'dataset_ids':[aid], 'code':'result = {}', 'assumptions':[assumption]}}}]}), 'test')
    run('F13','base')
    run('F14','base')
    assert len(calls) == 1
    assert h.state.factors['F13'].calculation_ids == h.state.factors['F14'].calculation_ids
    run('F14','downside')
    assert len(calls) == 2


def test_history_is_run_scoped_and_survives_resume(tmp_path):
    h = make(tmp_path)
    h.shared_work = SharedWork(h)
    raw = json.dumps({'actions':[{'factor_id':'F02', 'action':{
        'action':'search','reason':'history', 'query':'cash'}}]})
    apply_group_reply(h, ['F02'], raw, 'test')
    restored = SharedWork(h)
    assert restored.search('cash')
    h.state.source_revision = 'different_sources'
    assert not SharedWork(h).records


def test_deadline_stops_wait_without_discarding_existing_judgement(tmp_path):
    # Streamlit AppTest reloads grouped.py; resolve its current exception class.
    from credit_review.grouped import ReviewStopped
    h = make(tmp_path)
    apply_group_reply(h, ['F02'], json.dumps({'actions':[conclusion('F02')]}), 'test')
    class SlowClient:
        def next_actions(self, context):
            time.sleep(.15)
            return json.dumps({'actions':[conclusion('F04')]})
    h.client = SlowClient()
    started = time.monotonic()
    with pytest.raises(ReviewStopped, match='한도'):
        list(analyse_grouped(h, ['F02','F04'], time_budget=.05))
    assert time.monotonic()-started < .5
    assert h.state.factors['F02'].judgement
    assert h.state.factors['F04'].judgement is None
    time.sleep(.16)
    assert h.state.factors['F04'].judgement is None  # late reply cannot mutate shared state


def test_deadline_is_propagated_to_live_client():
    from credit_review.llm import ColabClient
    client = object.__new__(ColabClient)
    measured = MeasuredClient(client, Measurements())
    measured.set_deadline(time.monotonic()-1)
    with pytest.raises(TimeoutError):
        client.request_timeout()
