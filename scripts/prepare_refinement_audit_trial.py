"""Require correction traceability and reserve output inside the normal 32K budget."""
import json,shutil,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[1];old=root/'outputs/step_trials/C20.9s-step2-r3';out=root/'outputs/step_trials/C20.10s-step2-r1';out.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
request=read(old/'refinement.request.json');draft=read(old/'draft.json');ids=[p['id'] for p in draft['paragraphs']]
for check in request['structured_outputs']['json']['properties']['quality_checks']['properties'].values():
    check['properties']['affected_paragraph_ids']={'type':'array','items':{'type':'string','enum':ids},'maxItems':len(ids)}
    check['required'].append('affected_paragraph_ids');check['properties']['reason']['maxLength']=160
request['messages'][0]['content']+='\n검토 상태의 의미: supported는 원문과 일치하여 수정 불필요, corrected는 실제 revisions 또는 additions로 오류를 고친 경우만 사용한다. affected_paragraph_ids에는 corrected 판단으로 실제 내용이 변경되는 기존 문단 ID를 적는다. 아무 문단도 바꾸지 않는 검수는 corrected가 아니라 supported다. 동일한 값의 전후 비교(예: 120→120)는 오타 정정이 아니다. 짧은 이유에도 실제 비교 항목·기간·근거를 담고 점검했다는 선언만 쓰지 않는다. 네 품질 범주와 심층 검토 의무는 유지한다.'
config=read(root/'workspace/llm_connection.json');endpoint=config['base_url'].rstrip('/');endpoint=endpoint[:-3] if endpoint.endswith('/v1') else endpoint
payload={'model':config['model'],'messages':request['messages'],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}
started=time.perf_counter()
count=json.load(urllib.request.urlopen(urllib.request.Request(endpoint+'/tokenize',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+config['api_key'],'Content-Type':'application/json'}),timeout=30))['count']
request['max_tokens']=min(request['max_tokens'],32768-count-512)
if request['max_tokens']<1500:raise ValueError('Insufficient output budget; no input silently removed')
for name in ('draft.json','evidence.json'):shutil.copy2(old/name,out/name)
(out/'refinement.request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8')
audit={'version':'C20.10s','input_tokens':count,'output_reserved':request['max_tokens'],'safety_tokens':512,'context_limit':32768,'tokenize_seconds':time.perf_counter()-started,'source_content_preserved':True,'review_level':2,'end_to_end':False}
(out/'budget-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');print(audit)
