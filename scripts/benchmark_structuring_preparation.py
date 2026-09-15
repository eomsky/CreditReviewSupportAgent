"""Measure local cold DB/candidate preparation without repeating model calls."""
import json,sqlite3,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'outputs/step_trials/C20.7s/local-preparation'
out.mkdir(exist_ok=False)
document=root/'outputs/experiments/20260914/frozen/c102615852529efccd883325d9cb9be677598beac86490c65f6542d965f5216f.json'
commands=[['scripts/structuring_numeric_db.py',str(document),str(out/'numeric.sqlite')],['scripts/structuring_prepare_review.py','--folder',str(out)],['scripts/structuring_auxiliary.py','--folder',str(out)]]
timings=[];start=time.perf_counter()
for command in commands:
    before=time.perf_counter();result=subprocess.run([sys.executable,'-X','utf8',*command],cwd=root,capture_output=True,text=True,encoding='utf-8',check=True)
    timings.append({'task':command[0],'seconds':time.perf_counter()-before,'output':result.stdout.strip()})
elapsed=time.perf_counter()-start
def facts(path):
    db=sqlite3.connect(path)
    rows=db.execute('SELECT cell_id,account,period,unit,value_decimal,review_evidence FROM facts ORDER BY id').fetchall();db.close();return rows
same=facts(out/'numeric.sqlite')==facts(root/'outputs/step_trials/C20.6s/numeric.sqlite')
report={'seconds':elapsed,'calls':timings,'same_candidates_as_C20_6s':same,'scope':'cached parsed source JSON to pending numeric candidates; excludes original file parsing, joint request packing, model calls and final rendering','end_to_end':False}
(out/'timing.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
if not same:raise ValueError('Candidate drift')
