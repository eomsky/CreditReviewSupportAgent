"""Cashflow reuse plus newly retrieved collateral evidence for final report area."""
import copy,hashlib,json
from pathlib import Path
from accepted_evidence_bundle import build
from evidence_columnar import compact
from section_prompt_router import route

def main():
 root=Path(__file__).resolve().parents[1];out=root/'outputs/step_trials/C20.32-step15-input';out.mkdir(exist_ok=False)
 read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
 save=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 parent=root/'outputs/step_trials/C20.31-step14-input';g=read(parent/'step-result.json');assert g.get('allow_step15') and g['quality_status']=='pass'
 for n,h in g['artifact_sha256'].items():assert hashlib.sha256((parent/n).read_bytes()).hexdigest()==h
 baseline=root/'outputs/experiments/20260914/frozen/baseline_run'
 req=read(baseline/'report-part-2/report.request.json');req['messages'][0]['content'],audit=route(req['messages'][0]['content'],'report')
 prep=json.loads(read(baseline/'report-part-3/report.preparation.request.json')['messages'][1]['content'])
 ready=root/'outputs/step_trials/C20.32-step15-readiness';fresh=read(ready/'collateral-retrieval.json')
 sources=[];mapping={}
 for original in fresh['sources']:
  if original.get('page') not in [91,92,93,44]:continue
  source=copy.deepcopy(original);source['id']='S'+str(len(sources)+1);sources.append(source);mapping[original['id']]=source['id']
 sources,sections,lineage=build(root,sources,runs=['C20.25.2s-step8-replay'])
 catalog={f'A1P{i+1}':p for i,p in enumerate(sections[0]['paragraphs'])}
 cash=read(root/'outputs/step_trials/C20.25.2s-step8-replay/reviewed-artifact.json')
 cashrefs=list(dict.fromkeys(sid for p in sections[0]['paragraphs'] for sid in p['source_ids']))
 tables=[]
 for t in cash['tables']:
  t=copy.deepcopy(t);t.update(source_ids=cashrefs,report_template=True,after_paragraph_index=0);tables.append(t)
 facts=read(ready/'collateral-source-facts.json');facts['source_ids']=[mapping[s] for s in facts['source_ids']]
 collateral={'caption':'토지·건물 등 기존 담보 설정 내역 · 2025년 말','columns':['담보권자','통화·단위','설정액','차입액'],'rows':[[r['holder'],r['currency']+'('+r['unit']+')',r['collateral_amount'],r['borrowing_amount']] for r in facts['land_buildings']['pledges']], 'source_ids':facts['source_ids'],'report_template':True,'after_paragraph_index':0}
 fixtures={'상환능력':tables,'채권보전':[collateral],'종합 심사의견':[]}
 roles={'상환능력':['operating_cash','consolidated_cash','actual_repayment','forecast_financing'], '채권보전':['existing_collateral','guarantees_and_restrictions','loan_security_conditions'], '종합 심사의견':['repayment_balance','litigation_risk','decision_conditions']}
 schema={'type':'object','properties':{'sections':{'type':'array','minItems':3,'maxItems':3,'items':{'type':'object','properties':{'title':{'type':'string','enum':list(roles)},'paragraphs':{'type':'array','minItems':3,'maxItems':4,'items':{'type':'object','properties':{'role':{'type':'string','enum':[x for v in roles.values() for x in v]},'reuse_id':{'type':'string','enum':['']+list(catalog)},'text':{'type':'string'},'source_ids':{'type':'array','items':{'type':'string','enum':[s['id'] for s in sources]}}},'required':['role','reuse_id','text','source_ids'],'additionalProperties':False}}},'required':['title','paragraphs'],'additionalProperties':False}},'table_source_check':{'type':'string','enum':['supported','mismatch']}},'required':['sections','table_source_check'],'additionalProperties':False}
 payload={'documents':prep['documents'],'report_context':prep['report_context'],'reuse_catalog':catalog,'fixed_report_tables':fixtures,'collateral_facts_for_review':facts,'required_roles':roles}
 save(out/'original-source-archive.json',sources)
 for s in sources:s['text'],_=compact(s['text'])
 payload['sources']=sources
 req['messages'][1]['content']=json.dumps(payload,ensure_ascii=False);req['structured_outputs']['json']=schema
 req['messages'][0]['content']+='\n今回 호출은 상환능력·채권보전·종합 심사의견이다. required_roles를 각 목차에서 빠짐없이 한 번씩 작성한다. 상환능력 4역할은 검토 통과 reuse_catalog 상세문단을 선택하여 reuse_id를 쓰고 text는 빈 문자열, source_ids는 빈 배열로 반환한다. 나머지 6역할은 새 검색근거에 맞춰 독립된 분석문단을 작성하며 reuse_id는 빈 문자열, source_ids는 해당 원문 ID다. 이전 목차를 반복하지 말고 상환재원과 조달조건을 연결해 종합한다. 본건 신청금액·담보제공 확약·감정가·권리순위는 확인되지 않았으므로 최종 여신 가부나 잔여 담보여력을 확정하지 않는다. 기존 장부가액은 감정가/처분가가 아니다. 통화별 설정액을 합산하지 않으며 병합 장부가액은 한 번만 센다. 차입액·설정액·약정한도·보증금액은 서로 다른 개념이다. 소송청구금액은 확정손실이나 추가충당금이 아니다. 보증 제공과 보증 수취 방향을 구분한다. PDF의 소송/담보/약정 근거가 있으므로 미확인 또는 없다고 일반화하지 않는다. fixed_report_tables와 collateral_facts_for_review는 원문과 대조해 table_source_check를 반환한다. 표는 프로그램이 그대로 연결하며 새 표나 안내배너는 추가하지 않는다.'
 save(out/'generation.request.json',req);save(out/'reuse-catalog.json',catalog);save(out/'table-fixtures.json',fixtures);save(out/'lineage.json',lineage);save(out/'prompt-routing-audit.json',audit)
 save(out/'reuse-contract.json',{'step':15,'part':3,'roles_by_section':roles,'target_seconds':90,'allow_new_paragraphs':True,'retrieval_seconds':fresh['elapsed_seconds']})
 print(out)

if __name__=='__main__':main()
