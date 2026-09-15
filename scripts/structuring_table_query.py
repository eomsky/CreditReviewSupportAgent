"""Validated table identities and compact SQL table packets; never merge unknown bases."""
import json,sqlite3,hashlib,time,argparse,re
from decimal import Decimal
from pathlib import Path
root=Path(__file__).resolve().parents[1];old=root/'outputs/step_trials/C20.4s';out=root/'outputs/step_trials/C20.5s'
parser=argparse.ArgumentParser();parser.add_argument('--joint',action='store_true');parser.add_argument('--folder',type=Path);parser.add_argument('--base-request',type=Path);args=parser.parse_args()
if args.joint:out=root/'outputs/step_trials/C20.6s'
if args.folder:out=args.folder
response=json.loads((out/('joint-trial/attempt-001/response.json' if args.joint else 'metadata-trial-r2/attempt-001/response.json')).read_text());metadata=json.loads(response['choices'][0]['message']['content'])['tables']
candidates=json.loads((out/'metadata-candidates.json').read_text());by_id={t['table_id']:t for t in candidates}
if response['choices'][0]['finish_reason']!='stop' or len(metadata)!=len(by_id) or {t['table_id'] for t in metadata}!=set(by_id):raise ValueError('Incomplete metadata')
for m in metadata:
    if args.joint and (m['normalization_decision']!='approve' or m['normalization_issues']):raise ValueError('Joint normalization rejected')
    source=by_id[m['table_id']]['original_context']
    if m['evidence_quote'] not in source:raise ValueError('Unsupported table identity quote')
    if m['basis']!='unknown':
        quote=m['basis_evidence_quote']
        term='연결' if m['basis']=='consolidated' else '별도'
        if not quote or quote not in source or term not in quote:raise ValueError('Unsupported basis')
    elif m['basis_evidence_quote'] is not None:raise ValueError('Inconsistent basis')
if args.folder:
    c=sqlite3.connect(out/'numeric.sqlite')
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='table_metadata'").fetchone():raise FileExistsError('Already materialized')
else:
    if (out/'numeric.sqlite').exists():raise FileExistsError('Immutable candidate DB already exists')
    a=sqlite3.connect(old/'numeric.sqlite');c=sqlite3.connect(out/'numeric.sqlite');a.backup(c);a.close()
c.row_factory=sqlite3.Row
if args.joint:
    # Revalidate all raw locations; previous approvals are not evidence for this trial.
    facts=list(c.execute('SELECT * FROM facts'))
    expected=[fid for table in candidates for fid in table['fact_ids']]
    if len(expected)!=len(set(expected)) or set(expected)!={f['id'] for f in facts}:raise ValueError('Incomplete fact coverage')
    for f in facts:
        cell=c.execute('SELECT * FROM cells WHERE id=?',(f['cell_id'],)).fetchone();loc=json.loads(f['review_evidence'])
        if cell['source_id']!=loc['source_id'] or cell['column_name']+str(cell['row_number'])!=loc['cell']:raise ValueError('Cell mismatch')
        if Decimal(f['value_decimal'])!=Decimal(cell['numeric_lexeme']) or f['account']!=cell['row_label']:raise ValueError('Fact mismatch')
        for field in ('period','unit'):
            address=re.fullmatch(r'([A-Z]+)([0-9]+)',loc[field+'_cell'])
            rows=c.execute('SELECT raw_value FROM cells WHERE source_id=? AND column_name=? AND row_number=?',(loc.get(field+'_source_id',cell['source_id']),address[1],int(address[2]))).fetchall()
            if len(rows)!=1:raise ValueError('Ambiguous header')
            value=rows[0][0]
            if field=='unit':value=re.search(r'단위\s*:\s*([^)]*)',value)[1].split(',')[0].strip()
            elif re.match(r'20[0-9]{2}-[0-9]{2}',value):value=value[:7]
            if value!=f[field]:raise ValueError('Header mismatch')
    c.execute('DELETE FROM normalization_reviews')
    request_hash=hashlib.sha256((out/'joint.request.json').read_bytes()).hexdigest()
    for f in facts:
        c.execute('INSERT INTO normalization_reviews(fact_id,model,request_sha256,decision,reason) VALUES (?,?,?,?,?)',(f['id'],response['model'],request_hash,'approve','Joint table metadata and normalization review; raw cell validation passed'))
        c.execute("UPDATE facts SET review_status='approved' WHERE id=?",(f['id'],))
    (out/'joint-validation.json').write_text(json.dumps({'facts_checked':len(facts),'tables_checked':len(metadata),'request_sha256':request_hash,'basis_unknown_preserved':True},indent=2),encoding='utf-8')
c.executescript('CREATE TABLE table_metadata(table_id TEXT PRIMARY KEY,source_id TEXT,title_cell TEXT,table_type TEXT,basis TEXT,entity_hint TEXT,period_kind TEXT,evidence_quote TEXT); CREATE TABLE fact_table(fact_id INTEGER PRIMARY KEY,table_id TEXT);')
for m in metadata:
    original=by_id[m['table_id']]
    c.execute('INSERT INTO table_metadata VALUES (?,?,?,?,?,?,?,?)',(m['table_id'],original['source_id'],original['title_cell'],m['table_type'],m['basis'],m['entity'],m['period_kind'],m['evidence_quote']))
    for fact_id in original['fact_ids']:c.execute('INSERT INTO fact_table VALUES (?,?)',(fact_id,m['table_id']))
c.commit();sql='SELECT f.id,f.account,f.period,f.unit,f.value_decimal,f.source_id,f.row_number,f.column_name FROM approved_facts f JOIN fact_table t ON f.id=t.fact_id WHERE t.table_id=? ORDER BY f.account,f.period'
packets=[];audit=[];start=time.perf_counter()
for i,m in enumerate(metadata):
    rows=[dict(r) for r in c.execute(sql,(m['table_id'],))]
    compact={'table_id':m['table_id'],'table_type':m['table_type'],'basis':m['basis'],'entity_hint':m['entity'],'period_kind':m['period_kind'],'columns':['fact_id','account','period','unit','value'],'rows':[[r[k] for k in ['id','account','period','unit','value_decimal']] for r in rows]}
    packets.append({'id':'S'+str(i+1),'document_id':by_id[m['table_id']]['source_id'].rsplit('-c',1)[0],'text':json.dumps(compact,ensure_ascii=False,separators=(',',':'))})
    audit.append({'table_id':m['table_id'],'sql':sql,'parameters':[m['table_id']],'rows':rows})
c.close();query_seconds=time.perf_counter()-start
request=json.loads((args.base_request or old/'interpretation.request.json').read_text());user=json.loads(request['messages'][1]['content']);user['sources']=packets;request['messages'][1]['content']=json.dumps(user,ensure_ascii=False)
if not args.base_request:request['messages'][0]['content']+='\nSQL 결과는 표별로 분리되어 있다. table_id가 다르거나 basis가 unknown이면 같은계정·같은수치여도 서로 다른 기준일 수 있어 임의로 합치지 않는다. entity_hint는 문서명에서 얻은 힌트일 뿐 각 표의 보고주체 확정이 아니다. fixed summary 표와 상세표를 설명할 때 표별 기간·수치를 유지한다. 현재 값으로 계산 가능한 지표는 정의를 명확히 하고 출처 표를 붙인다.'
allowed=[p['id'] for p in packets]
def update(node):
    if isinstance(node,dict):
        if node.get('enum') and all(isinstance(x,str) and x.startswith('S') and x[1:].isdigit() for x in node['enum']):node['enum']=allowed
        for v in node.values():update(v)
    elif isinstance(node,list):
        for v in node:update(v)
if not args.base_request:update(request['structured_outputs'])
(out/'interpretation.request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8');(out/'sql-query-audit.json').write_text(json.dumps({'queries':audit,'seconds':query_seconds,'basis_unknown_tables':[m['table_id'] for m in metadata if m['basis']=='unknown']},ensure_ascii=False,indent=2),encoding='utf-8')
print({'tables':len(packets),'rows':sum(len(t['rows']) for t in audit),'query_seconds':query_seconds})
