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
            plan=schema['$defs']['PreparedDataset']
            assert 'after_dataset' in plan['required']
            assert plan['properties']['after_dataset']=={'$ref':'#/$defs/DatasetCalculation'}
            return json.dumps({'datasets':[{'dataset':{
                'name':'cash','description':'cash','entity':'Example','scope':'CONSOLIDATED',
                'value_type':'ACTUAL','columns':[{'name':'period','dtype':'string'},{'name':'cash','dtype':'number','unit':'KRW'}],
                'period_column':'period','records':[{'cells':[
                    {'column':'period','value':'2025','source_ids':['R1']},
                    {'column':'cash','value':10,'source_ids':['R1']}]}]},
                'after_dataset':None}], 'limitations':[]})
    reply=json.loads(prepare_financial(Client(),{'sources':{'source_id':{'text':'2025 cash 10 KRW'}}}))
    assert reply['datasets'][0]['dataset']['cell_sources']==[{'period':['source_id'],'cash':['source_id']}]


def test_bundle_reference_arrays_cannot_repeat_until_token_limit():
    class Client:
        def complete(self,prompt,context,schema,request_options):
            judgement=schema['$defs']['Judgement']['properties']
            assert judgement['evidence_ids']['maxItems']==2
            assert judgement['calculation_ids']['maxItems']==0
            required=judgement['requirements']
            assert set(required['properties'])==set(FACTORS['F27']['required_evidence'])
            assert required['additionalProperties'] is False
            assert all(p['maxItems']==2 for p in required['properties'].values())
            assert judgement['missing']['maxItems']==6
            return '{"findings":[],"requests":[]}'
    review_bundle(Client(),{'sources':{'a':{},'b':{}},'datasets':{},'calculations':{},
                            'factors':{'F27':FACTORS['F27']}})


def test_quality_pass_rejection_retains_draft_and_is_not_reported_complete(tmp_path):
    h=make(tmp_path)
    class Client:
        def set_deadline(self,deadline): pass
        def prepare_financial(self,context): return '{"datasets":[],"limitations":[]}'
        def review_bundle(self,context):
            return json.dumps({'findings':[{'factor_id':fid,'judgement':{
                'summary':'Original supported limitation',
                'evidence_ids':['nonexistent'] if fid=='F17' and context['review_pass'] else [],
                'missing':['Sources not provided']}} for fid in context['factors']]})
    h.client=Client()
    list(analyse_prepared(h,list(FACTORS),time_budget=30,concurrency=2))
    review=json.loads((h.store.path/'quality_review.json').read_text())
    assert review['status']=='PARTIAL'
    assert review['unresolved']==['F17']
    assert h.state.factors['F17'].judgement.summary=='Original supported limitation'


def test_ordered_bundle_cannot_borrow_another_factors_requirement_keys():
    class Client:
        def complete(self,prompt,context,schema,request_options):
            array=schema['properties']['findings']
            assert array['items'] is False
            for item,fid in zip(array['prefixItems'],['F27','F29']):
                assert item['properties']['factor_id']['enum']==[fid]
                keys=item['properties']['judgement']['properties']['requirements']['properties']
                assert set(keys)==set(FACTORS[fid]['required_evidence'])
            return '{"findings":[],"requests":[]}'
    review_bundle(Client(),{'sources':{'a':{}},'datasets':{},'calculations':{},
                            'factors':{fid:FACTORS[fid] for fid in ['F27','F29']}})


def test_overall_risk_uses_revised_findings_after_quality_pass(tmp_path):
    h=make(tmp_path); observed=[]
    class Client:
        def set_deadline(self,deadline): pass
        def prepare_financial(self,context): return '{"datasets":[],"limitations":[]}'
        def review_bundle(self,context):
            if list(context['factors'])==['F30']:
                observed.append(context['prior_findings']['F17']['summary'])
            return json.dumps({'findings':[{'factor_id':fid,'judgement':{
                'summary':'Revised liquidity limitation' if context['review_pass'] else 'Initial draft',
                'evidence_ids':[],'missing':['Limited evidence']}} for fid in context['factors']]})
    h.client=Client()
    list(analyse_prepared(h,list(FACTORS),time_budget=30,concurrency=2))
    assert observed==['Revised liquidity limitation']
