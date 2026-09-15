"""Materialize a trial with SQL-verified fixed cells and complete generated prose."""
import argparse,copy,json,sqlite3,time
from decimal import Decimal
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--reference',required=True);a=p.parse_args()
start=time.perf_counter();folder=Path(a.folder)
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
response=read(folder/'interpretation-trial/attempt-001/response.json')
if response['choices'][0]['finish_reason']!='stop':raise ValueError('Incomplete response')
body=json.loads(response['choices'][0]['message']['content'])
tables=copy.deepcopy(read(Path(a.reference)/'state.json')['views']['financial_accounts']['tables'])
db=sqlite3.connect(folder/'numeric.sqlite');db.row_factory=sqlite3.Row
audit=[]
for table in tables:
    source=table['source_binding']['source_id']
    for row in table['rows']:
        for i,period in enumerate(table['columns'][1:],1):
            matches=list(db.execute('SELECT * FROM approved_facts WHERE source_id=? AND account=? AND period=?',(source,row[0],period)))
            if len(matches)!=1 or Decimal(matches[0]['value_decimal'])!=Decimal(str(row[i])):raise ValueError('Fixed template SQL mismatch')
            row[i]=int(Decimal(matches[0]['value_decimal']))
            audit.append({'fact_id':matches[0]['id'],'source_id':source,'account':row[0],'period':period,'cell':matches[0]['column_name']+str(matches[0]['row_number'])})
paragraphs=body['paragraphs']+[body['earnings_highlight_including_tax'],body['earnings_explanation_including_tax']]+list(body['analysis_paragraphs'].values())
request=read(folder/'interpretation.request.json');sources=json.loads(request['messages'][1]['content'])['sources'];ids={s['id'] for s in sources}
if any(not x['source_ids'] or not set(x['source_ids'])<=ids for x in paragraphs):raise ValueError('Unresolved citation')
artifact={'title':body['title'],'tables':tables,'paragraphs':paragraphs,'sources':sources,'required_document_reviews':body['required_document_reviews']}
lines=[body['title'],'']
for table in tables:
    lines += [table['caption'],' | '.join(table['columns'])]
    lines += [' | '.join(f'{v:,}' if isinstance(v,int) else str(v) for v in row) for row in table['rows']]
for item in paragraphs:lines+=['',item['heading'],item['text'],'근거: '+', '.join(item['source_ids'])]
(folder/'materialized-artifact.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
(folder/'full-output.txt').write_text('\n'.join(lines),encoding='utf-8')
# Flexible document record: preserve metadata and original source separately from SQL facts.
records=[]
for meta in db.execute('SELECT * FROM table_metadata'):
    original=db.execute('SELECT raw_text FROM sources WHERE id=?',(meta['source_id'],)).fetchone()
    facts=[dict(r) for r in db.execute('SELECT f.* FROM approved_facts f JOIN fact_table t ON f.id=t.fact_id WHERE t.table_id=?',(meta['table_id'],))]
    records.append({'metadata':dict(meta),'original_context':original[0],'facts':facts})
(folder/'table-documents.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
db.close()
result={'fixed_cells_verified':len(audit),'paragraphs':len(paragraphs),'citation_ids_resolve':True,'cells':audit,'seconds':time.perf_counter()-start,'quality_status':'requires_semantic_review','end_to_end':False}
(folder/'materialization-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print({k:v for k,v in result.items() if k!='cells'})
