import json
import pytest
from threading import Event
from test_harness import make
from credit_review.prepared import analyse_prepared, evidence_pack
from credit_review.prepared_client import alias_context, prepare_financial, review_bundle
from credit_review.registry import FACTORS


def test_compact_shared_page_keeps_exact_scope_text_and_original():
    from copy import deepcopy
    from credit_review.prepared_client import compact_page_contexts
    opening={'source_id':'page1','text':'연결 재무상태표 (단위:천원)','excerpt_only':True}
    context={'sources':{sid:{'id':sid,'text':sid+' values','document_id':'doc','page':1,
        'table_index':{'page_opening':opening,'locator':{'source_id':sid,'document_id':'doc','page':1},
                       'tables':[{'units':['천원']}]}} for sid in ['a','b']}}
    original=deepcopy(context)
    compact=compact_page_contexts(context)
    assert context==original
    assert compact['page_contexts']=={'page1':opening}
    for sid in context['sources']:
        s=compact['sources'][sid]
        assert s['text']==context['sources'][sid]['text']
        assert s['table_index']['page_context_id']=='page1'
        assert s['table_index']['tables']==context['sources'][sid]['table_index']['tables']
    wire,restore=alias_context(compact)
    assert json.loads(restore(json.dumps(wire)))==compact


def test_aliases_restore_reference_keys_and_lists_without_changing_text():
    value={'sources':{'long_source':{'id':'long_source','text':'long_source appears in prose'}},
           'calculations':{'long_calc':{'result':1}}, 'references':['long_source','long_calc']}
    compact,restore=alias_context(value)
    assert set(compact['sources'])=={'R1'}
    assert compact['sources']['R1']['text']=='long_source appears in prose'
    assert json.loads(restore(json.dumps(compact)))==value


@pytest.mark.parametrize('concurrency',[1,2,3,4])
def test_numeric_bundles_wait_and_overall_sees_previous_findings(tmp_path,concurrency):
    h=make(tmp_path)
    foundation=Event()
    class Client:
        def set_deadline(self,deadline): pass
        def prepare_financial(self,context):
            foundation.set()
            return '{"datasets":[],"limitations":["fixture has no extracted statement"]}'
        def review_bundle(self,context):
            ids=list(context['factors'])
            if 'F13' in ids: assert foundation.is_set()
            if ids==['F30']: assert len(context['prior_findings'])==29
            return json.dumps({'findings':[{'factor_id':fid,'judgement':{
                'summary':'Evidence is limited; repayment capacity is not established.',
                'evidence_ids':[], 'missing':['financial and contractual evidence']}} for fid in ids], 'requests':[]})
    h.client=Client()
    events=list(analyse_prepared(h,list(FACTORS),time_budget=10,concurrency=concurrency))
    assert all(f.judgement for f in h.state.factors.values())
    assert all(f.status=='PARTIALLY_FULFILLED' for f in h.state.factors.values())
    assert any(e['kind']=='heartbeat' or e['kind']=='state' for e in events)


def test_delivered_sources_are_complete_and_respect_budget(tmp_path):
    h=make(tmp_path)
    pack=evidence_pack(h,['F24'],budget=1)
    assert pack['sources']=={}
    assert pack['omitted_source_ids']
    assert not h.state.factors['F24'].read_source_ids


def test_foundation_wire_pairing_preserves_each_rows_sources():
    from credit_review.demo import DemoClient
    # Capture the generated schema without making a network call.
    class Client:
        def complete(self,prompt,context,schema,request_options):
            assert 'records' in schema['$defs']['Dataset']['properties']
            return json.dumps({'datasets':[{'dataset':{
                'name':'cash','description':'cash','entity':'Example','scope':'CONSOLIDATED',
                'value_type':'ACTUAL','columns':[{'name':'period','dtype':'string'},{'name':'cash','dtype':'number','unit':'KRW'}],
                'period_column':'period','records':[{'values':{'period':'2025','cash':10},'sources':{'period':['R1'],'cash':['R1']}}]},
                'after_dataset':None}], 'limitations':[]})
    reply=json.loads(prepare_financial(Client(),{'sources':{'source_id':{'text':'2025 cash 10 KRW'}}}))
    assert reply['datasets'][0]['dataset']['cell_sources']==[{'period':['source_id'],'cash':['source_id']}]
