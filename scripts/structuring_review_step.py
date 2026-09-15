"""Measure preparation, 32K guard, model review and metadata-aware application."""
import argparse,json,sys,time,shutil,hashlib,subprocess,urllib.request
from pathlib import Path
from step_trial import initialize,trial
args=argparse.ArgumentParser()
args.add_argument('--version',default='C20.10.1s')
args.add_argument('--run-id',default='C20.10.1s-step2-r1')
args.add_argument('--extra-instructions',type=Path)
args.add_argument('--context-audit',action='store_true')
args.add_argument('--complete-income-table',action='store_true')
a=args.parse_args()
root=Path(__file__).resolve().parents[1];base=root/'outputs/step_trials/C20.10s-step2-r1';out=root/'outputs/step_trials'/a.run_id;out.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
began=time.perf_counter()
request=read(base/'refinement.request.json')
if a.extra_instructions:
    extra=a.extra_instructions.read_text(encoding='utf-8-sig')
    request['messages'][0]['content']+='\n'+extra
    (out/'extra-instructions.txt').write_text(extra,encoding='utf-8')
for name in ('draft.json','evidence.json'):shutil.copy2(base/name,out/name)
if a.complete_income_table:
    from structuring_income_completion import augment as complete_income
    request,evidence,candidates=complete_income(request,read(out/'evidence.json'),root/'outputs/step_trials/C20.8s-cold-r1/numeric.sqlite')
    save(out/'evidence.json',evidence);save(out/'supplemental-candidates.json',candidates)
if a.context_audit:
    from structuring_context_audit import augment
    request=augment(request,read(out/'draft.json'),read(out/'evidence.json'))
files=['structuring_review_step.py','structuring_apply_refinement.py','structuring_metadata_guard.py','step_trial.py']
if a.context_audit:files.append('structuring_context_audit.py')
if a.complete_income_table:files.append('structuring_income_completion.py')
(out/'source-snapshot').mkdir()
hashes={name:hashlib.sha256((root/'scripts'/name).read_bytes()).hexdigest() for name in files}
for name in files:shutil.copy2(root/'scripts'/name,out/'source-snapshot'/name)
save(out/'source-manifest.json',hashes)
config=read(root/'workspace/llm_connection.json');endpoint=config['base_url'].rstrip('/');endpoint=endpoint[:-3] if endpoint.endswith('/v1') else endpoint
payload={'model':config['model'],'messages':request['messages'],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}
count=json.load(urllib.request.urlopen(urllib.request.Request(endpoint+'/tokenize',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+config['api_key'],'Content-Type':'application/json'}),timeout=30))['count']
request['max_tokens']=min(8000,32768-count-512)
if request['max_tokens']<1500:raise ValueError('Insufficient output space')
save(out/'refinement.request.json',request);save(out/'budget-audit.json',{'input':count,'output':request['max_tokens'],'safety':512,'limit':32768})
initialize(out/'trial',out/'refinement.request.json',50)
preparation=time.perf_counter()-began
call=trial(out/'trial',root/'outputs/frozen_candidates/C20.4-step2-r1')
if call['status']=='fail':raise RuntimeError('Model review failed')
if a.complete_income_table:
    state=read(out/'trial/state.json');response=read(out/'trial'/state['attempts'][-1]/'response.json')
    normalized=json.loads(response['choices'][0]['message']['content'])['supplemental_normalization']
    if normalized['decision']!='approve' or normalized['issues']:raise ValueError('Supplemental normalization rejected')
    save(out/'supplemental-approval.json',{'decision':normalized,'candidates':candidates,'response_sha256':hashlib.sha256(json.dumps(response).encode()).hexdigest()})
subprocess.run([sys.executable,'-X','utf8','scripts/structuring_apply_refinement.py',str(out)],cwd=root,check=True)
if any(hashlib.sha256((root/'scripts'/name).read_bytes()).hexdigest()!=digest for name,digest in hashes.items()):raise ValueError('Code changed during measurement')
elapsed=time.perf_counter()-began
result={'version':a.version,'status':'completed','step':2,'preparation_seconds':preparation,'model_seconds':call['elapsed_seconds'],'elapsed_seconds':elapsed,'target_seconds':50,'time_status':'pass' if elapsed<=50 else 'provisional_pass' if elapsed<=70 else 'fail','quality_status':'unassessed','allow_step3':False,'end_to_end':False,'scope':'accepted ga draft and approved SQL evidence to reviewed artifact; step1 cost excluded'}
save(out/'step-result.json',result);print(json.dumps(result,ensure_ascii=False))
