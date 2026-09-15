"""Apply reviewed candidates only after lexical and location validation."""
import json,sqlite3,hashlib,re,time
from decimal import Decimal
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=root/'outputs/step_trials/C20.4s'
response=json.loads((folder/'auxiliary-trial/attempt-001/response.json').read_text())
decision=json.loads(response['choices'][0]['message']['content'])
if response['choices'][0]['finish_reason']!='stop' or decision['decision']!='approve' or decision['issues']:raise ValueError('Normalization needs correction')
c=sqlite3.connect(folder/'numeric.sqlite');c.row_factory=sqlite3.Row
facts=list(c.execute("SELECT * FROM facts WHERE review_status='pending'"))
for f in facts:
    cell=c.execute('SELECT * FROM cells WHERE id=?',(f['cell_id'],)).fetchone()
    locator=json.loads(f['review_evidence'])
    if cell['source_id']!=locator['source_id'] or cell['column_name']+str(cell['row_number'])!=locator['cell']:raise ValueError('Cell mismatch')
    if Decimal(f['value_decimal'])!=Decimal(cell['numeric_lexeme']):raise ValueError('Value mismatch')
    if f['account']!=cell['row_label']:raise ValueError('Account mismatch')
    for field,column in [('period','period_cell'),('unit','unit_cell')]:
        match=re.fullmatch(r'([A-Z]+)([0-9]+)',locator[column])
        raw=c.execute('SELECT raw_value FROM cells WHERE source_id=? AND column_name=? AND row_number=?',(locator.get(field+'_source_id',cell['source_id']),match[1],int(match[2]))).fetchall()
        if len(raw)!=1:raise ValueError('Ambiguous metadata location')
        value=raw[0][0]
        if field=='unit':value=re.search(r'단위\s*:\s*([^)]*)',value)[1].split(',')[0].strip()
        if field=='period':value=re.match(r'20[0-9]{2}-[0-9]{2}',value)[0]
        if f[field]!=value:raise ValueError('Metadata mismatch')
request_hash=hashlib.sha256((folder/'auxiliary.request.json').read_bytes()).hexdigest()
for f in facts:
    c.execute('INSERT INTO normalization_reviews(fact_id,model,request_sha256,decision,reason) VALUES (?,?,?,?,?)',(f['id'],response['model'],request_hash,decision['decision'],decision['reason']))
    c.execute("UPDATE facts SET review_status='approved' WHERE id=?",(f['id'],))
c.commit()
query='SELECT account,period,unit,value_decimal,source_id,row_number,column_name FROM approved_facts WHERE account=? AND period=?'
params=('금융비용','추정1기');start=time.monotonic();rows=[dict(r) for r in c.execute(query,params)];elapsed=time.monotonic()-start
(folder/'auxiliary-query-example.json').write_text(json.dumps({'sql':query,'params':params,'rows':rows,'elapsed_seconds':elapsed,'normalization_rows_checked':len(facts),'scope':'fixed financial accounts table only','full_step1_completed':False},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'approved':len(facts),'query_rows':rows,'query_seconds':elapsed},ensure_ascii=False))
c.close()
