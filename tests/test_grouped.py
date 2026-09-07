import json
from datetime import date
from threading import Lock
import pytest

from credit_review.models import Action
from credit_review.grouped import analyse_grouped, apply_group_reply, group_context
from credit_review.parallel import Measurements, MeasuredClient
from credit_review.harness import Harness
from credit_review.demo import demo_sources
from credit_review.retrieval import Retriever
from test_harness import make


def test_one_batch_produces_two_validated_sections_without_individual_calls(tmp_path):
    class Client:
        calls = 0
        def next_actions(self, context):
            self.calls += 1
            return json.dumps({'actions':[{'factor_id':fid, 'action':{
                'action':'conclude', 'reason':'qualified', 'judgement':{
                    'summary':'근거 범위에 한정한 검토', 'evidence_ids':[], 'missing':['identity not verified']}}}
                for fid in context['factors']]})
        def next_action(self, context):
            raise AssertionError('Completed factors must not be reanalysed')
    client, metrics = Client(), Measurements()
    h = Harness.create(tmp_path, 'group', date(2026,4,7), demo_sources(), MeasuredClient(client, metrics))
    events = list(analyse_grouped(h, ['F01','F02'], metrics=metrics))
    assert client.calls == 1
    assert metrics.snapshot()['llm_calls'] == 1
    assert all(h.state.factors[fid].judgement for fid in ['F01','F02'])
    assert sum(e['kind']=='state' and bool(e['value'].judgement) for e in events) >= 2
    assert metrics.first_report_seconds is not None


def test_batch_schema_requires_nonnull_payload_for_every_action():
    from credit_review.llm import ColabClient
    client = object.__new__(ColabClient)
    captured = {}
    def complete(prompt, context, schema):
        captured.update(schema)
        return '{}'
    client.complete = complete
    client.next_actions({'factors':{'F01':{}}})
    branches = captured['$defs']['Action']['anyOf']
    assert len(branches) == 8
    for branch in branches:
        assert len(branch['required']) == 3
        payload = branch['required'][-1]
        assert 'anyOf' not in branch['properties'][payload]
    plan = next(b for b in branches if b['properties']['action']['enum']==['plan'])
    assert 'inquiry' in plan['required']


def test_group_dataset_and_executed_result_share_without_reextraction(tmp_path):
    h = make(tmp_path)
    for _ in range(2):
        h.step('F24')
    data_id = h.state.factors['F24'].dataset_ids[0]
    dataset = h.store.get(data_id)['payload']
    ids = ['F13','F14']
    for fid in ids:
        h.state.factors[fid].evidence_ids = list(h.state.factors['F24'].evidence_ids)
    apply_group_reply(h, ids, json.dumps({'actions':[{'factor_id':'F13','action':{
        'action':'dataset','reason':'shared','dataset':dataset}}]}), 'test')
    shared = h.state.factors['F13'].dataset_ids[-1]
    assert h.state.factors['F14'].dataset_ids == [shared]
    apply_group_reply(h, ids, json.dumps({'actions':[{'factor_id':'F13','action':{
        'action':'calculate','reason':'execute','calculation':{'purpose':'ratio',
            'dataset_ids':[shared],'code':'result = {}'}}}]}), 'test')
    calc = h.state.factors['F13'].calculation_ids[-1]
    assert h.state.factors['F14'].calculation_ids == [calc]
    assert h.store.get(calc)['payload']['status'] == 'EXECUTED'
    context = group_context(h, ids)
    assert list(context['datasets']) == [shared]
    assert list(context['calculations']) == [calc]


def test_group_rejects_foreign_factor_and_unknown_evidence(tmp_path):
    h = make(tmp_path)
    action = {'action':'conclude','reason':'bad','judgement':{'summary':'bad','evidence_ids':['invented']}}
    with pytest.raises(ValueError, match='Unexpected'):
        apply_group_reply(h, ['F13'], json.dumps({'actions':[{'factor_id':'F14','action':action}]}), 'test')
    with pytest.raises(ValueError, match='unavailable'):
        apply_group_reply(h, ['F13'], json.dumps({'actions':[{'factor_id':'F13','action':action}]}), 'test')
    assert h.state.factors['F13'].judgement is None


def test_unresolved_group_uses_adaptive_search_instead_of_forced_conclusion(tmp_path):
    class Client:
        individual = 0
        def next_actions(self, context):
            return 'not JSON'
        def next_action(self, context):
            self.individual += 1
            return json.dumps({'action':'conclude','reason':'qualified','judgement':{
                'summary':'자료 범위 제한', 'evidence_ids':[], 'missing':['unknown']}})
    client = Client()
    h = Harness.create(tmp_path, 'fallback', date(2026,4,7), demo_sources(), client)
    list(analyse_grouped(h, ['F01']))
    assert client.individual == 1 and h.state.factors['F01'].judgement


def test_index_reuse_does_not_reuse_changed_content_or_future_evidence():
    rows = demo_sources()
    first = Retriever(rows, date(2026,4,7))
    second = Retriever(rows, date(2026,4,7))
    assert first.sparse is second.sparse
    changed = [r.model_copy(update={'text':r.text+' changed'}) for r in rows]
    assert Retriever(changed, date(2026,4,7)).sparse is not first.sparse
    future = [r.model_copy(update={'published_at':date(2027,1,1)}) for r in rows]
    assert not Retriever(future, date(2026,4,7)).search('현금')


def test_upload_cache_reuses_extraction_across_dates_and_single_flight(tmp_path, monkeypatch):
    import credit_review.ingestion as ingestion
    calls = []
    def extract(path, published, artifacts):
        calls.append(path)
        return [r.model_copy(update={'published_at':published}) for r in demo_sources()]
    monkeypatch.setattr(ingestion, 'from_pdf_isolated', extract)
    one = ingestion.prepare_upload(tmp_path, b'same pdf', 'original.pdf', date(2026,3,31))
    two = ingestion.prepare_upload(tmp_path, b'same pdf', 'renamed.pdf', date(2026,3,31))
    assert one is two
    assert one.result(timeout=5)['sources']
    later = ingestion.prepare_upload(tmp_path, b'same pdf', 'original.pdf', date(2026,4,1)).result(timeout=5)
    assert len(calls) == 1 and later['cached']
    assert all(r['published_at']=='2026-04-01' for r in later['sources'])
