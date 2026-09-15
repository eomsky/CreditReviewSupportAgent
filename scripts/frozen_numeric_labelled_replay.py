"""Focused source-reference replay; never an end-to-end result."""
import copy,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/frozen_candidates/C6/code/scripts'))
import llm_stream,semantic_table_review as semantic
from frozen_numeric_cells import numbered,schema_cells,restore,scoped_evidence
from frozen_numeric_cells_patch import RULE
from frozen_review_reason_bound import bound_schema
out=ROOT/'outputs/frozen_candidates/C7-numeric-labelled-replay';out.mkdir(exist_ok=False)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(n,v):(out/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
req=read(ROOT/'outputs/frozen_candidates/C6/calls/022.request.json')
body=json.loads(req['messages'][1]['content'])
tables=read(ROOT/'outputs/frozen_candidates/C6/run/cashflow_repayment.memory.json')['draft']['tables']
tables=[t for t in tables if not t.get('source_binding')]
body['sources']=scoped_evidence(tables,body['sources'])
aliases={s['id']:copy.deepcopy(s) for s in body['sources']}
body['tables']=[semantic.input_table(t) for t in tables]
body['evidence_assessment']={}
req['structured_outputs']['json']=semantic.schema(tables,list(aliases),['2023','2024','2025'])
req['structured_outputs']['json']=bound_schema(schema_cells(req['structured_outputs']['json'],tables,list(aliases)))
req['messages'][0]['content']+='\n'+RULE
for s in body['sources']:s['text']=numbered(s['text'])
req['messages'][1]['content']=json.dumps(body,ensure_ascii=False)
save('request.json',req)
started=time.monotonic()
def progress(d,t):(out/'stream.txt').write_text(t,encoding='utf-8')
try:
 response=llm_stream.complete(read(ROOT/'workspace/llm_connection.json'),req,progress,timeout=600)
 save('response.json',response)
 decoded=semantic.plain_addresses(json.loads(response['choices'][0]['message']['content'],strict=False))
 audit=restore(decoded,tables,aliases);save('cell-audit.json',audit);save('decoded.json',decoded)
 rows=decoded['T0']['rows']
 actual=[[row['values'].get(f'C{i}') for i in range(1,4)] for row in rows.values()]
 expected=[[None,243067,415848],[None,-605426,-821459],[None,397118,699927],[None,247041,546282]]
 result={'status':'completed','elapsed_seconds':time.monotonic()-started,'end_to_end':False,'actual':actual,'eight_cells_period_unit_passed':actual==expected,'usage':response.get('usage')}
 save('results.json',result);print(json.dumps(result),flush=True)
except Exception as e:
 save('results.json',{'status':'failed','error':str(e),'elapsed_seconds':time.monotonic()-started,'end_to_end':False});raise
