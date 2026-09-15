"""Build a generation request from SQL-approved facts, preserving provenance."""
import json,sqlite3,time
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=root/'outputs/step_trials/C20.4s'
started=time.perf_counter();c=sqlite3.connect(folder/'numeric.sqlite');c.row_factory=sqlite3.Row
sql='SELECT account,period,unit,value_decimal,entity,basis,source_id,row_number,column_name FROM approved_facts ORDER BY account,period,source_id,row_number'
rows=[dict(r) for r in c.execute(sql)];c.close()
grouped={}
for r in rows:
    key=(r['account'],r['period'],r['unit'],r['entity'],r['basis'])
    g=grouped.setdefault(key,{'account':r['account'],'period':r['period'],'unit':r['unit'],'value':r['value_decimal'],'entity':r['entity'],'basis':r['basis'],'locators':[]})
    if g['value']!=r['value_decimal']:raise ValueError('Conflicting source values; review required')
    g['locators'].append({'source_id':r['source_id'],'cell':r['column_name']+str(r['row_number'])})
sources=[]
for i,g in enumerate(grouped.values()):
    sources.append({'id':'S'+str(i+1),'document_id':g['locators'][0]['source_id'].rsplit('-c',1)[0],'text':json.dumps(g,ensure_ascii=False)})
request=json.loads((root/'outputs/frozen_candidates/C20.4-step1-r1/run/financial_accounts.request.json').read_text())
user=json.loads(request['messages'][1]['content']);user['sources']=sources;user['prior_model_drafts']={}
request['messages'][1]['content']=json.dumps(user,ensure_ascii=False)
request['messages'][0]['content']+='\n이번 실험의 sources는 LLM 정규화 검수와 원문셀 대조를 거친 SQL 조회값이다. 수치는 이 조회 결과만 사용하고 계산은 입력값으로 검산한다. locators는 실제 원문셀 근거이다. basis/entity null은 미확정이며 별도/연결을 임의로 붙이지 않는다. SQL에 없는 상세 수치나 조달용도를 만들지 않는다. 영업성과·손익연결·자본·단기상환·전망의 해석에 집중한다.'
allowed=[s['id'] for s in sources]
def aliases(node):
    if isinstance(node,dict):
        if 'enum' in node and node['enum'] and all(isinstance(x,str) and x.startswith('S') and x[1:].isdigit() for x in node['enum']):node['enum']=allowed
        for value in node.values():aliases(value)
    elif isinstance(node,list):
        for value in node:aliases(value)
aliases(request['structured_outputs'])
(folder/'interpretation.request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8')
(folder/'sql-dataset.json').write_text(json.dumps({'sql':sql,'facts':list(grouped.values()),'source_rows':len(rows),'query_build_seconds':time.perf_counter()-started,'raw_sources_omitted_from_interpretation':True},ensure_ascii=False,indent=2),encoding='utf-8')
print({'approved_rows':len(rows),'unique_facts':len(sources)})
