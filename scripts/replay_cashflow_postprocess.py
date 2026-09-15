"""Replay the failed table response through existing validation without generation."""
import copy,json,sys,threading,time
from pathlib import Path
from types import SimpleNamespace
from frozen_numeric_cells import restore

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/frozen_candidates/C11-r1'
OUT=ROOT/'outputs/step_trials/cashflow-postprocess'
OUT.mkdir(parents=True,exist_ok=False)
sys.path[:0]=[str(BASE/'code/scripts'),str(BASE/'harness')]
import semantic_table_review as review
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
memory=read(BASE/'run/cashflow_repayment.memory.json')
recorded=read(BASE/'run/cashflow_repayment.table-review.request.json')
response=read(BASE/'run/cashflow_repayment.table-review.response.json')
body=json.loads(recorded['messages'][1]['content'])
# The saved request is the authoritative input to the failed step. Its draft
# table may have changed after the earlier memory checkpoint.
tables=[t for t in memory['draft']['tables'] if not t.get('source_binding')]
assert len(tables)==len(body['tables'])
for target,original in zip(tables,body['tables']):
    for key in ('columns','rows','caption'):target[key]=copy.deepcopy(original[key])
def saved_response(*args,**kwargs):
    actual=json.loads(args[2]['messages'][1]['content'])
    assert actual['sources']==body['sources'],'Replay source selection changed'
    assert actual['tables']==body['tables'],'Replay table input changed'
    return copy.deepcopy(response)
review.llm_recovery.complete=saved_response
review.restore_numeric_cells=restore
app=SimpleNamespace(lock=threading.RLock(),config=lambda:{'model':recorded['model']},dump=save)
started=time.monotonic()
result=review.review(app,None,None,OUT,'cashflow_repayment',memory,{'run':{}},None)
table=next(t for t in result['tables'] if t['caption'].startswith('현금흐름표'))
expected=[[None,243067,415848],[None,-605426,-821459],[None,397118,699927],[None,247041,546282]]
assert [r[1:] for r in table['rows']]==expected
assert table['semantic_review_completed'] and not table.get('verification_gaps')
save(OUT/'verification.json',{'end_to_end':False,'generation_called':False,
    'elapsed_seconds':time.monotonic()-started,'postprocessing_pass':True,
    'scope':'Saved table response through source materialization, fixed-table integrity and layout application',
    'body_quality_assessed':False})
print('Postprocessing passed; 8 values/periods/units preserved; no generation')
