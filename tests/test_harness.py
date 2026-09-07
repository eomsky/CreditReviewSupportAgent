import json
from datetime import date
import pytest
from credit_review.demo import DemoClient, demo_sources
from credit_review.harness import Harness
from credit_review.models import Action, Source, Dataset
from credit_review.retrieval import Retriever

class FixtureExecutor:
    def execute(self, plan, datasets):
        row = next(iter(datasets.values()))['rows'][0]
        return {'status': 'EXECUTED', 'executor': 'test_fixture', 'result': {
            'historical_cf_to_maturity': row['operating_cf'] / row['maturing_debt'],
            'cash_after_maturity': row['cash'] - row['maturing_debt']}}

def make(tmp_path):
    return Harness.create(tmp_path, 'test', date(2026,4,7), demo_sources(), DemoClient(), 'DEMO', executor=FixtureExecutor())

def test_chain_and_resume(tmp_path):
    h = make(tmp_path)
    for _ in range(4): h.step('F24')
    f = h.state.factors['F24']
    assert f.error is None
    assert f.status == 'PARTIALLY_FULFILLED'
    assert len(f.dataset_ids) == len(f.calculation_ids) == 1
    assert h.store.get(f.calculation_ids[0])['payload']['result']['cash_after_maturity'] == -50
    report = h.synthesize()
    assert report['status'] == 'DRAFT_ONLY' and len(report['unanalysed']) == 29
    resumed = Harness.resume(tmp_path, 'test', h.state.run_id, DemoClient(), FixtureExecutor())
    assert resumed.state.factors['F24'] == f
    before = len(h.store.artifacts())
    resumed.reset_factor('F24')
    assert resumed.state.report_id is None
    assert len(h.store.artifacts()) > before

def test_future_excluded_from_read_and_search():
    future = Source(id='future', document_id='future', page=1, text='현금흐름', published_at=date(2027,1,1))
    r = Retriever(demo_sources()+[future], date(2026,4,7))
    assert all(h['source']['id'] != 'future' for h in r.search('현금흐름'))
    with pytest.raises(ValueError): r.read(['future'])

def test_bad_provenance_and_scope(tmp_path):
    h = make(tmp_path)
    h.step('F24')
    action = Action.model_validate_json(DemoClient().next_action(h.context('F24')))
    action.dataset.cell_sources[0]['cash'] = ['invented']
    with pytest.raises(ValueError): h.apply('F24', action, 'test')
    action.dataset.cell_sources[0]['cash'] = ['demo_cash']
    action.dataset.scope = 'UNKNOWN'
    with pytest.raises(ValueError): h.apply('F24', action, 'test')

def test_bad_json_logged(tmp_path):
    h = make(tmp_path)
    h.client.next_action = lambda _: 'not json'
    h.step('F24')
    assert h.state.factors['F24'].status == 'ERROR'
    assert any(a['stage'] == 'llm_output' for a in h.store.artifacts())
    assert not (h.store.path / '.step.lock').exists()

def test_bad_judgement_reference(tmp_path):
    h = make(tmp_path)
    bad = Action(action='conclude', reason='test', judgement={'summary':'x','evidence_ids':['invented']})
    with pytest.raises(ValueError): h.apply('F24', bad, 'test')

def test_no_progress(tmp_path):
    h = make(tmp_path)
    h.client.next_action = lambda _: json.dumps({'action':'search','reason':'same','query':'cash'})
    for _ in range(4): h.step('F24')
    assert h.state.factors['F24'].status == 'NO_PROGRESS'

def test_row_requires_provenance():
    with pytest.raises(ValueError):
        Dataset(name='x',description='x',entity='x',scope='SEPARATE',value_type='ACTUAL',
                columns=[{'name':'year','dtype':'string'}],rows=[{'year':'2025'}],cell_sources=[{}],period_column='year')

def test_unit_required_for_numeric_input(tmp_path):
    h = make(tmp_path)
    h.step('F24')
    action = Action.model_validate_json(DemoClient().next_action(h.context('F24')))
    action.dataset.columns[1].unit = None
    with pytest.raises(ValueError, match='unit'):
        h.apply('F24', action, 'test')

def test_path_traversal(tmp_path):
    with pytest.raises(ValueError):
        Harness.create(tmp_path,'../escape',date(2026,4,7),demo_sources(),DemoClient())
