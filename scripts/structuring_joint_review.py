"""C20.6s joint normalization and identity review over shared original excerpts."""
import json,sqlite3,time,argparse
from pathlib import Path
root=Path(__file__).resolve().parents[1];old=root/'outputs/step_trials/C20.4s';prior=root/'outputs/step_trials/C20.5s';out=root/'outputs/step_trials/C20.6s';out.mkdir(exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path);args=parser.parse_args()
schema_template=prior/'metadata-r2.request.json'
if args.folder:old=prior=out=args.folder
c=sqlite3.connect(old/'numeric.sqlite');c.row_factory=sqlite3.Row
candidates=json.loads((prior/'metadata-candidates.json').read_text());source_ids=set();facts=[]
for f in c.execute('SELECT * FROM facts'):
    loc=json.loads(f['review_evidence']);source_ids.update([loc['source_id'],loc.get('period_source_id',loc['source_id']),loc.get('unit_source_id',loc['source_id'])]);facts.append((dict(f),loc))
source_ids.update(t['source_id'] for t in candidates);aliases={id:'R'+str(i+1) for i,id in enumerate(sorted(source_ids))}
raw=[{'id':aliases[id],'sheet':row['sheet'],'text':row['raw_text']} for id in sorted(source_ids) for row in [c.execute('SELECT * FROM sources WHERE id=?',(id,)).fetchone()]]
for t in candidates:
    t['context_source']=aliases[t['source_id']];t.pop('original_context')
    t['normalized_rows']=[[f['id'],f['account'],f['period'],f['unit'],f['value_decimal'],aliases[loc['source_id']],loc['cell'],aliases[loc.get('period_source_id',loc['source_id'])],loc['period_cell'],aliases[loc.get('unit_source_id',loc['source_id'])],loc['unit_cell']] for f,loc in facts if f['id'] in t['fact_ids']]
c.close()
req=json.loads(schema_template.read_text());item=req['structured_outputs']['json']['properties']['tables']['items'];item['properties']['normalization_decision']={'type':'string','enum':['approve','reject']};item['properties']['normalization_issues']={'type':'array','items':{'type':'integer'}};item['required']+=['normalization_decision','normalization_issues']
req['messages'][0]['content']+=' 동시에 각 표의 모든 정규화행을 원문 셀과 대조한다. 행 구조는 [fact_id,계정,기간,단위,값,값출처,값셀,기간출처,기간셀,단위출처,단위셀]이다. 숫자·부호·단위·기간·계정·좌표 중 잘못 대응된 항목은 normalization_issues에 fact_id를 쓰고 reject한다. 모든 후보가 정확할 때만 approve와 빈 issues를 반환한다. 검수 항목을 생략하지 않는다.'
req['messages'][1]['content']=json.dumps({'tables':candidates,'original_sources':raw},ensure_ascii=False,separators=(',',':'))
(out/'joint.request.json').write_text(json.dumps(req,ensure_ascii=False,indent=2),encoding='utf-8');(out/'metadata-candidates.json').write_text((prior/'metadata-candidates.json').read_text(),encoding='utf-8');(out/'source-map.json').write_text(json.dumps(aliases,ensure_ascii=False,indent=2),encoding='utf-8');print({'raw_sources':len(raw),'tables':len(candidates),'facts':len(facts)})
