"""Prepare financial report areas using accepted interpretations and tables."""
import copy,hashlib,json
from pathlib import Path
from accepted_evidence_bundle import build
from evidence_columnar import compact
from section_prompt_router import route

def main():
    root=Path(__file__).resolve().parents[1];out=root/'outputs/step_trials/C20.31-step14-input';out.mkdir(exist_ok=False)
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    save=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    parent=root/'outputs/step_trials/C20.30.3.1-step13-replay';gate=read(parent/'step-result.json')
    assert gate['quality_status']=='pass' and gate['allow_step14']
    for name,digest in gate['artifact_sha256'].items():assert hashlib.sha256((parent/name).read_bytes()).hexdigest()==digest
    baseline=root/'outputs/experiments/20260914/frozen/baseline_run/report-part-2'
    req=read(baseline/'report.request.json');payload=json.loads(req['messages'][1]['content'])
    req['messages'][0]['content'],routing=route(req['messages'][0]['content'],'report')
    runs=['C20.13.1s-step2-replay','C20.18.1s-step4-r1','C20.24s-step6-r1']
    sources,sections,lineage=build(root,payload['sources'],runs=runs)
    catalog={};fixtures={'수익성':[],'재무안정':[]};table_lineage=[]
    for i,(section,run) in enumerate(zip(sections,runs)):
        for j,p in enumerate(section['paragraphs']):catalog[f'A{i+1}P{j+1}']=p
        original=read(root/'outputs/step_trials'/run/'reviewed-artifact.json')
        for table in original['tables']:
            t=copy.deepcopy(table);t['source_ids']=list(dict.fromkeys(sid for p in section['paragraphs'] for sid in p['source_ids']))
            t['report_template']=True;t['after_paragraph_index']=0
            t['caption']=['주요 재무계정 및 전망 (단위: 백만원)','수익성 지표 및 전망 (단위: %, 배)','재무안정성 및 자산 관련 지표 (단위: %)'][i]
            target='수익성' if i==1 else '재무안정';fixtures[target].append(t)
            table_lineage.append({'run':run,'original_table':table,'original_values_preserved':True})
    fixtures['재무안정'][1]['after_paragraph_index']=2
    payload['prior_model_drafts']=sections;payload['reuse_catalog']=catalog;payload['fixed_report_tables']=fixtures
    payload['prepared_context']['tables']=[]
    roles={'수익성':['sales_and_margin','financing_cost','earnings_bridge','forecast_profitability'], '재무안정':['assets_and_debt','capital_and_short_debt','liquidity_structure','asset_quality','forecast_stability']}
    descriptions={'sales_and_margin':'매출성장·원가율·영업이익률','financing_cost':'금융비용 및 이자보상배율','earnings_bridge':'세전이익·법인세·순손실 상세 연결','forecast_profitability':'추정 수익성/금융비용 부담','assets_and_debt':'자산과 차입의 증가 및 조달 용도 확인 한계','capital_and_short_debt':'자본 감소와 단기차입 부담','liquidity_structure':'유동비율과 장기자본 구조','asset_quality':'매출채권·재고 비율만으로 회수/부실 확정 불가','forecast_stability':'추정 지표 및 차환 확인 필요'}
    schema=req['structured_outputs']['json'];schema['properties'].pop('planned_tables');schema['required'].remove('planned_tables')
    schema['properties']['table_source_check']={'type':'string','enum':['supported','mismatch']};schema['required'].append('table_source_check')
    schema['properties']['sections']['items']['properties']['paragraphs']={'type':'array','items':{'type':'object','properties':{'role':{'type':'string','enum':list(descriptions)},'reuse_id':{'type':'string','enum':list(catalog)}},'required':['role','reuse_id'],'additionalProperties':False},'minItems':4,'maxItems':5}
    payload['required_reuse_roles']=descriptions
    save(out/'original-source-archive.json',sources)
    for source in sources:source['text'],_=compact(source['text'])
    payload['sources']=sources
    req['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
    req['messages'][0]['content']+='\n이번 호출은 수익성·재무안정 보고서 영역이다. 본문을 새로 쓰지 말고 reuse_catalog에서 각 required_reuse_roles에 맞는 문단ID를 선택한다. 프로그램이 검토 통과 문장과 출처를 그대로 연결한다. 수익성은 sales_and_margin/financing_cost/earnings_bridge/forecast_profitability, 재무안정은 assets_and_debt/capital_and_short_debt/liquidity_structure/asset_quality/forecast_stability를 모두 한 번씩 채운다. 단순 요약문보다 수치·의미·확인한계가 충분한 상세문단을 선택한다. 중복 ID는 금지한다. fixed_report_tables는 검토 통과표를 수치/단위/기간 그대로 삽입한다. 근거 일치 여부는 table_source_check로 검수하고 planned_tables는 작성하지 않는다. 표별 원문 작성기준의 차이를 섞어 산식을 새로 만들지 않는다. 원문이나 승인 해석의 불확실성을 임의 확정하지 않는다.'
    save(out/'generation.request.json',req);save(out/'reuse-catalog.json',catalog);save(out/'table-fixtures.json',fixtures)
    save(out/'reuse-contract.json',{'step':14,'part':2,'roles_by_section':roles,'target_seconds':90})
    save(out/'lineage.json',lineage);save(out/'table-lineage.json',table_lineage);save(out/'prompt-routing-audit.json',routing)
    print(out)

if __name__=='__main__':main()
