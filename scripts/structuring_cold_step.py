"""One measured step from cached extraction, including fresh normalization calls."""
import argparse,json,subprocess,sys,time,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('run_id');a=p.parse_args()
if not a.run_id.startswith('C20.8s-') or Path(a.run_id).name!=a.run_id:raise ValueError('Invalid run id')
out=root/'outputs/step_trials'/a.run_id;out.mkdir(exist_ok=False)
reference=root/'outputs/frozen_candidates/C20.4-step1-r1'
base=root/'outputs/step_trials/C20.8s'
document=root/'outputs/experiments/20260914/frozen/c102615852529efccd883325d9cb9be677598beac86490c65f6542d965f5216f.json'
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
timings=[];began=time.perf_counter()
def run(script,*args):
    save(out/'progress.json',{'current':script,'elapsed_seconds':time.perf_counter()-began})
    t=time.perf_counter();r=subprocess.run([sys.executable,'-X','utf8','scripts/'+script,*map(str,args)],cwd=root,capture_output=True,text=True,encoding='utf-8')
    timings.append({'task':script,'seconds':time.perf_counter()-t,'exit_code':r.returncode})
    if r.returncode:raise RuntimeError(script+' failed')
def model(name,request):
    run('step_trial.py','init',out/name,out/request,'--target','70')
    run('step_trial.py','run',out/name,'--code',reference)
    if read(out/name/'attempt-001/result.json')['status']=='fail':raise RuntimeError(name+' failed')
try:
    run('structuring_numeric_db.py',document,out/'numeric.sqlite')
    run('structuring_prepare_review.py','--folder',out)
    run('structuring_auxiliary.py','--folder',out)
    run('structuring_table_metadata.py','--folder',out)
    run('structuring_joint_review.py','--folder',out)
    model('joint-trial','joint.request.json')
    run('structuring_table_query.py','--joint','--folder',out,'--base-request',base/'interpretation.request.json')
    # No schema weakening relative to the reviewed candidate is permitted.
    current=read(out/'interpretation.request.json');prior=read(base/'interpretation.request.json')
    if current['structured_outputs']!=prior['structured_outputs'] or current['messages'][0]!=prior['messages'][0]:raise ValueError('Prompt/schema drift')
    model('interpretation-trial','interpretation.request.json')
    run('structuring_materialize_trial.py',out,'--reference',reference)
    elapsed=time.perf_counter()-began
    result={'status':'completed','elapsed_seconds':elapsed,'target_seconds':70,'time_status':'pass' if elapsed<=70 else 'provisional_pass' if elapsed<=110 else 'fail','quality_status':'unassessed','allow_step2':False,'end_to_end':False,'scope':'cached extraction to completed ga draft; original file extraction and vector indexing excluded','timings':timings}
except Exception as exc:
    result={'status':'failed','error_type':type(exc).__name__,'elapsed_seconds':time.perf_counter()-began,'timings':timings,'allow_step2':False,'end_to_end':False}
save(out/'step-result.json',result);save(out/'progress.json',{'current':'terminal','status':result['status']});print(json.dumps(result,ensure_ascii=False))
