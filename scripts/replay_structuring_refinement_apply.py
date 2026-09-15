"""Replay an actual frozen review response to validate the new application adapter."""
import json,sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];old=root/'outputs/frozen_candidates/C20.4-step2-r1';out=root/'outputs/step_trials/refinement-apply-replay'
out.mkdir(exist_ok=False);attempt=out/'trial/attempt-001';attempt.mkdir(parents=True)
sys.path.insert(0,str(old/'code/scripts'));import review_refinement as ref
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
memory=read(old/'run/financial_accounts.refinement.memory.json');draft=memory['draft'];sources=memory['compressed_sources']
ids={f'P{i+1}':p['id'] for i,p in enumerate(draft['paragraphs'])}
ids.update({f'S{i+1}':s['id'] for i,s in enumerate(sources)});ids.update({f'D{i+1}':d['id'] for i,d in enumerate(memory['documents'])})
response=read(old/'run/financial_accounts.refinement.response.json')
response['choices'][0]['message']['content']=json.dumps(ref.remap_ids(json.loads(response['choices'][0]['message']['content']),ids),ensure_ascii=False)
save(out/'draft.json',draft);save(out/'evidence.json',sources);save(attempt/'response.json',response);save(out/'trial/state.json',{'attempts':['attempt-001']})
subprocess.run([sys.executable,'-X','utf8','scripts/structuring_apply_refinement.py',str(out)],cwd=root,check=True)
actual=read(out/'reviewed-artifact.json');expected=read(old/'run/financial_accounts.refinement.result.json')
checks={'paragraph_texts_match_frozen':[(p['id'],p['text']) for p in actual['paragraphs']]==[(p['id'],p['text']) for p in expected['paragraphs']], 'tables_match_frozen':actual['tables']==expected['tables']}
save(out/'replay-result.json',{'checks':checks,'model_calls':0,'scope':'application mechanics; not semantic quality','end_to_end':False})
if not all(checks.values()):raise ValueError('Replay differs')
print(checks)
