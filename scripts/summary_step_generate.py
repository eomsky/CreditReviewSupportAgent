"""Warm summary generation comparison; upstream preparation is explicitly excluded."""
import json,time,hashlib,urllib.request,copy
from pathlib import Path
from step_trial import initialize,trial
from section_prompt_router import route
import summary2_structure,prepared_context
root=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
 budget=read(root/'workspace/step_time_budget.json');target=budget['targets_seconds']['11'];ceiling=budget.get('summary_generation_provisional_ceiling_seconds',target+budget['temporary_overrun_seconds'])
 t=time.perf_counter();out=root/'outputs/step_trials/C20.28.3-step11-r1';out.mkdir(exist_ok=False)
 parent=root/'outputs/step_trials/C20.27.1.1s-step10-replay';g=read(parent/'step-result.json')
 if not g.get('allow_step11') or g['quality_status']!='pass':raise ValueError('Step10 not accepted')
 for n,h in g['artifact_sha256'].items():
  if hashlib.sha256((parent/n).read_bytes()).hexdigest()!=h:raise ValueError('Parent modified')
 baseline=root/'outputs/experiments/20260914/frozen/baseline_run'
 req=read(baseline/'summary_2.request.json');req['messages'][0]['content'],audit=route(req['messages'][0]['content'],'summary2')
 payload=json.loads(req['messages'][1]['content']);sources=payload['sources']
 from accepted_evidence_bundle import build
 sources,sections,lineage=build(root,sources)
 from evidence_columnar import compact
 save(out/'original-source-archive.json',sources)
 compression=[]
 for source in sources:
  original=source['text'];source['text'],changed=compact(original)
  compression.append({'source_id':source['id'],'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'before_chars':len(original),'after_chars':len(source['text']),'lossless':True})
 save(out/'source-encoding-audit.json',compression)
 reusable={}
 for si,section in enumerate(sections):
  for pi,paragraph in enumerate(section['paragraphs']):
   paragraph['reuse_id']=f'A{si+1}P{pi+1}';reusable[paragraph['reuse_id']]=copy.deepcopy(paragraph)
 save(out/'reuse-catalog.json',reusable)
 payload['sources']=sources;payload['accepted_section_context']=sections
 payload['accepted_context_rules']='승인 본문은 해석 참고이며 사실 근거는 연결된 sources다. 기존 준비요약과 원문이 충돌하면 원문 기준을 구분한다. 이미 확인된 실적·전망 상환재원을 자료 미제공이라고 단정하지 않는다. 금액 기준·기간을 섞지 않는다.'
 req['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
 def aliases(node):
  if isinstance(node,dict):
   if node.get('enum') and all(isinstance(x,str) and x.startswith('S') and x[1:].isdigit() for x in node['enum']):node['enum']=[s['id'] for s in sources]
   for v in node.values():aliases(v)
  elif isinstance(node,list):
   for v in node:aliases(v)
 aliases(req['structured_outputs']['json'])
 save(out/'accepted-context-lineage.json',lineage)
 req['messages'][0]['content']+='\n이미 검증된 가~마 논점을 종합하되 동일한 설명을 여러 목차에 반복하지 않는다. 종속회사 표는 기업명/소재지/지분율/업종으로만 구성되어 금액 단위가 없다. unit은 빈 문자열이어야 한다. 주요 재무현황 표는 명시된 결산기간과 연결/별도 기준을 보존한다.'
 req['structured_outputs']['json']['properties']['planned_tables']['properties']['T0']['properties']['unit']={'type':'string','enum':['']}
 slots={'earnings_bridge':'영업이익·영업외손익·세전이익·법인세·순손익을 연결한 상세 문단','capital_and_liquidity':'자본변동 및 단기 상환부담','actual_repayment':'최근 실적의 현금흐름과 원리금 상환여력','forecast_financing':'추정 조달전후 현금흐름·기초기말 잔액·조달조건'}
 slot_schema={'type':'object','properties':{k:{'type':'string','enum':list(reusable),'description':v} for k,v in slots.items()},'required':list(slots),'additionalProperties':False}
 req['structured_outputs']['json']['properties']['topics']['properties']['t6']['properties']['paragraphs']=slot_schema
 payload['required_reuse_coverage']=slots
 req['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
 req['messages'][0]['content']+='\n종합의견 t6 paragraphs는 역할별 reuse_id를 반환하는 객체다. earnings_bridge는 세전이익·법인세·순손익 연결을 설명한 상세문단을 반드시 선택하며 단순 매출추세 문단으로 대체하지 않는다. capital_and_liquidity, actual_repayment, forecast_financing도 각 설명에 맞는 서로 다른 승인문단을 선택한다. 프로그램이 검증된 문단 원문과 출처를 보존해 연결한다. t0~t5에서는 전체 재무제표의 손익·차입 인과·상환가능성을 새로 분석하지 않는다. t4는 사업모델·제품·고객구성·수주 및 확인한계에 집중하고 t6 재무분석을 반복하지 않는다. 일반차입은 우발채무 자체가 아니다. 유동비율만으로 자체현금흐름 상환불능을 단정하지 않는다. __evidence_records_v1__은 원문 JSON의 반복 레코드를 columns/rows로 무손실 표현한 것으로 열순서대로 대응한다.'
 config=read(root/'workspace/llm_connection.json');ep=config['base_url'].rstrip('/');ep=ep[:-3] if ep.endswith('/v1') else ep
 headers={'Authorization':'Bearer '+config['api_key'],'Content-Type':'application/json'}
 count=json.load(urllib.request.urlopen(urllib.request.Request(ep+'/tokenize',data=json.dumps({'model':config['model'],'messages':req['messages'],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}).encode(),headers=headers),timeout=30))['count']
 models=json.load(urllib.request.urlopen(urllib.request.Request(ep+'/v1/models',headers=headers),timeout=15))['data']
 limit=min(65536,int(next((m.get('max_model_len',32768) for m in models if m['id']==config['model']),32768)))
 req['max_tokens']=min(12000,limit-count-512)
 if req['max_tokens']<3000:raise ValueError('Input budget insufficient')
 save(out/'generation.request.json',req);save(out/'prompt-routing-audit.json',audit);save(out/'budget-audit.json',{'input':count,'output':req['max_tokens'],'limit':limit,'reserve':512})
 initialize(out/'generation-trial',out/'generation.request.json',target)
 result=trial(out/'generation-trial',root/'outputs/frozen_candidates/C20.4-step2-r1',timeout=180)
 if result['status']=='fail':
  save(out/'step-result.json',{'step':11,'version':'C20.28.3','status':'failed','quality_status':'unassessed','elapsed_seconds':time.perf_counter()-t,'allow_step12':False,'end_to_end':False});return
 response=read(out/'generation-trial/attempt-001/response.json');body=json.loads(response['choices'][0]['message']['content'])
 selected=[body['topics']['t6']['paragraphs'][role] for role in slots]
 if len(selected)!=len(set(selected)):raise ValueError('Duplicate reused paragraph')
 body['topics']['t6']['paragraphs']=[copy.deepcopy(reusable[k]) for k in selected]
 save(out/'reuse-selection.json',{'selected':selected,'text_and_citations_exact':True})
 summary2_structure.flatten(body)
 packet=read(baseline/'summary_2.preparation.json')
 prepared_context.apply(body,packet,{s['id']:s for s in sources});body['sources']=sources
 from summary_table_layout import improve
 save(out/'table-layout-audit.json',improve(body['tables']))
 save(out/'materialized-artifact.json',body)
 (out/'full-output.txt').write_text('\n\n'.join([body['title']]+[p['heading']+'\n'+p['text'] for p in body['paragraphs']]+[t['caption']+'\n'+' | '.join(t['columns'])+'\n'+'\n'.join(' | '.join(str(c) for c in row) for row in t['rows']) for t in body['tables']]),encoding='utf-8')
 elapsed=time.perf_counter()-t
 save(out/'step-result.json',{'step':11,'version':'C20.28.3','status':'completed','quality_status':'unassessed','target_seconds':target,'elapsed_seconds':elapsed,'time_status':'pass' if elapsed<=target else 'provisional_pass' if elapsed<=ceiling else 'fail','allow_step12':False,'end_to_end':False,'scope':'warm frozen source/plan replay; retrieval and preprocessing excluded'})
 print(json.dumps(read(out/'step-result.json')))
if __name__=='__main__':main()
