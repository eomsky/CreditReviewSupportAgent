import json
import pytest
from threading import Lock
from time import sleep
from test_harness import make
from credit_review.prepared import analyse_prepared, evidence_pack, review_context
from credit_review.models import Judgement
from credit_review.prepared_client import alias_context, prepare_financial, review_bundle
from credit_review.registry import FACTORS
from credit_review.report_plan import REPORT_SECTIONS, REPORT_FACTOR_ORDER
from credit_review.section_prompts import GLOBAL_REPORT_STYLE_PROMPT, SECTION_REPORT_PROMPTS


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


@pytest.mark.parametrize('concurrency',[1,2,4])
def test_report_sections_are_called_once_in_dependency_waves(tmp_path,concurrency):
    h=make(tmp_path)
    calls=[]
    class Client:
        def set_deadline(self,deadline): pass
        def review_bundle(self,context):
            calls.append(context['report_section']['title'])
            ids=list(context['factors'])
            assert context['single_pass'] is True
            return json.dumps({'findings':[{'factor_id':fid,'judgement':{
                'summary':'Evidence is limited; repayment capacity is not established.',
                'evidence_ids':[], 'missing':['financial and contractual evidence']}} for fid in ids], 'requests':[]})
    h.client=Client()
    events=list(analyse_prepared(h,list(FACTORS),time_budget=10,concurrency=concurrency))
    assert len(calls)==len(REPORT_SECTIONS)==7
    assert set(calls)=={section['title'] for section in REPORT_SECTIONS}
    assert set(calls[:4])=={'업체현황','여신 개요 및 신청 사유','사업 분석','재무 분석'}
    assert set(calls[4:6])=={'주요 리스크 분석','상환재원'}
    assert calls[6]=='특이사항'
    assert all(f.judgement for f in h.state.factors.values())
    assert all(f.status=='PARTIALLY_FULFILLED' for f in h.state.factors.values())
    assert any(e['kind']=='state' for e in events)
    assert not list(h.store.path.glob('quality_review.json'))
    assert not list((h.store.path/'artifacts').glob('prepared_foundation_input_*.json'))


def test_parallel_sections_overlap_and_later_waves_receive_prior_findings(tmp_path):
    h=make(tmp_path)
    guard=Lock()
    active=0
    maximum=0
    received={}
    class Client:
        def set_deadline(self,deadline): pass
        def review_bundle(self,context):
            nonlocal active,maximum
            number=context['report_section']['number']
            received[number]=set(context['prior_findings'])
            with guard:
                active+=1
                maximum=max(maximum,active)
            sleep(.03)
            with guard:
                active-=1
            return json.dumps({'findings':[{'factor_id':fid,'judgement':{
                'summary':'근거 범위에서 조건부 취급이 타당함.',
                'evidence_ids':[], 'missing':['추가 확인 필요함']}} for fid in context['factors']], 'requests':[]})
    h.client=Client()
    list(analyse_prepared(h,list(FACTORS),time_budget=10,concurrency=2))
    assert maximum==2
    assert received[1]==received[2]==received[3]==received[5]==set()
    assert {'F06','F13'} <= received[4]
    assert {'F27','F13'} <= received[6]
    assert {'F30','F24'} <= received[7]


def test_delivered_sources_are_complete_and_respect_budget(tmp_path):
    h=make(tmp_path)
    pack=evidence_pack(h,['F24'],budget=1)
    assert pack['sources']=={}
    assert pack['omitted_source_ids']
    assert not h.state.factors['F24'].read_source_ids


def test_later_section_receives_compact_prior_findings(tmp_path):
    h=make(tmp_path)
    h.state.factors['F01'].judgement=Judgement(
        summary='Earlier conclusion', evidence_ids=['source-a'],
        risks=['Earlier risk'], mitigants=['Earlier mitigant'],
        missing=['large internal checklist'], conflicts=['large internal conflict'],
        requirements={'company_identity':['source-a']})
    prior=review_context(h,['F02'])['prior_findings']['F01']
    assert prior=={
        'summary':'Earlier conclusion',
        'risks':['Earlier risk'],
        'mitigants':['Earlier mitigant'],
    }


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
            assert schema['properties']['requests']['maxItems']==0
            return '{"findings":[],"requests":[]}'
    review_bundle(Client(),{'sources':{'a':{},'b':{}},'datasets':{},'calculations':{},
                            'factors':{'F27':FACTORS['F27']},'single_pass':True,
                            'report_section':{'number':2,'title':'여신 개요 및 신청 사유','blocks':['신청내용']}})


def test_every_single_pass_section_receives_reference_report_prompt():
    prompts=[]
    class Client:
        def complete(self,prompt,context,schema,request_options):
            prompts.append(prompt)
            return '{"findings":[],"requests":[]}'
    for section in REPORT_SECTIONS:
        review_bundle(Client(),{
            'sources':{},'datasets':{},'calculations':{},'single_pass':True,
            'factors':{fid:FACTORS[fid] for fid in section['factor_ids']},
            'report_section':section,
        })
    assert len(prompts)==7
    for section,prompt in zip(REPORT_SECTIONS,prompts):
        assert GLOBAL_REPORT_STYLE_PROMPT in prompt
        assert SECTION_REPORT_PROMPTS[section['number']] in prompt
        assert f"【{section['number']}." in prompt
        assert '심사자는 단순 요약자가 아니라 여신 판단의 책임 주체임' in prompt
        assert '모든 문장 어미는' in prompt
        assert '요인당 3~5문장을 사용한다' in prompt
        assert '내부 근거 ID는 evidence_ids에만 기록' in prompt
    assert '914,339,580천원을 9.14억원으로 축약하지 않으며' in prompts[5]
    assert '각 소제목을 중복 없이 3~4문장으로 완결' in prompts[4]
    assert '승인·조건부 승인·감액·만기조정·보류·부결' in prompts[6]


def test_initial_numeric_bundle_thinking_is_opt_in_and_separate_from_review(monkeypatch):
    options=[]
    class Client:
        def complete(self,prompt,context,schema,request_options):
            options.append(request_options)
            return '{"findings":[],"requests":[]}'
    monkeypatch.setenv('CREDIT_BUNDLE_THINKING','1')
    monkeypatch.setenv('CREDIT_BUNDLE_THINKING_BUDGET','1536')
    monkeypatch.setenv('CREDIT_REVIEW_THINKING','0')
    for fid,review in [('F14',False),('F02',False),('F14',True)]:
        review_bundle(Client(),{'sources':{},'datasets':{},'calculations':{},
                               'factors':{fid:FACTORS[fid]},'review_pass':review})
    assert [x['chat_template_kwargs']['enable_thinking'] for x in options]==[True,False,False]
    assert options[0]['thinking_token_budget']==1536
    assert 'thinking_token_budget' not in options[1]


def test_failed_section_is_not_reinferred_on_resume(tmp_path):
    h=make(tmp_path)
    calls=[]
    class Client:
        def set_deadline(self,deadline): pass
        def review_bundle(self,context):
            calls.append(context['report_section']['number'])
            if context['report_section']['number']==1:
                raise TimeoutError('first section timeout')
            return json.dumps({'findings':[{'factor_id':fid,'judgement':{
                'summary':'Original supported limitation', 'evidence_ids':[],
                'missing':['Sources not provided']}} for fid in context['factors']]})
    h.client=Client()
    list(analyse_prepared(h,list(FACTORS),time_budget=30,concurrency=2))
    assert len(calls)==7 and set(calls)==set(range(1,8))
    list(analyse_prepared(h,list(FACTORS),time_budget=30,concurrency=2))
    assert len(calls)==7 and set(calls)==set(range(1,8))
    assert json.loads((h.store.path/'section_01_attempt.json').read_text(encoding='utf-8'))['status']=='FAILED'


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


def test_report_plan_covers_every_factor_once():
    assert len(REPORT_FACTOR_ORDER)==30
    assert tuple(dict.fromkeys(REPORT_FACTOR_ORDER))==REPORT_FACTOR_ORDER
    assert set(REPORT_FACTOR_ORDER)==set(FACTORS)
