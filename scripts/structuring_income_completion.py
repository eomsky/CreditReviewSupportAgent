"""Locate omitted operating result within an already identified income table."""
import copy,json,re,sqlite3
from pathlib import Path

def augment(request,evidence,db):
    request=copy.deepcopy(request);evidence=copy.deepcopy(evidence)
    c=sqlite3.connect(f'file:{Path(db).as_posix()}?mode=ro',uri=True);c.row_factory=sqlite3.Row
    candidates=[]
    for source in evidence:
        table=json.loads(source['text'])
        if table.get('table_type')!='income_statement':continue
        tid=table['table_id'];meta=c.execute('SELECT * FROM table_metadata WHERE table_id=?',(tid,)).fetchone()
        if not meta:continue
        facts=c.execute('SELECT f.*,cl.row_number FROM facts f JOIN fact_table t ON f.id=t.fact_id JOIN cells cl ON cl.id=f.cell_id WHERE t.table_id=?',(tid,)).fetchall()
        sheet=c.execute('SELECT sheet FROM sources WHERE id=?',(meta['source_id'],)).fetchone()[0]
        start=int(re.search(r'\d+$',meta['title_cell'])[0]);end=max(f['row_number'] for f in facts)
        rows=c.execute('SELECT cl.* FROM cells cl JOIN sources s ON s.id=cl.source_id WHERE s.sheet=? AND cl.row_number BETWEEN ? AND ? ORDER BY cl.row_number,cl.id',(sheet,start,end)).fetchall()
        wanted=[r for r in rows if re.sub(r'\s|\(손실\)','',r['raw_value'])=='영업이익']
        for label in wanted:
            for period in sorted({f['period'] for f in facts}):
                anchor=next(f for f in facts if f['period']==period)
                loc=json.loads(anchor['review_evidence']);col=re.match('[A-Z]+',loc['period_cell'])[0]
                matches=[r for r in rows if r['row_number']==label['row_number'] and r['column_name']==col and r['numeric_lexeme'] is not None]
                if len(matches)!=1:continue
                value=matches[0]
                if any(r[1]==label['raw_value'] and r[2]==period for r in table['rows']):continue
                header=c.execute('SELECT raw_value FROM cells WHERE source_id=? AND column_name=? AND row_number=?',(loc['period_source_id'],col,int(re.search(r'\d+$',loc['period_cell'])[0]))).fetchone()[0]
                candidate={'id':'cell-'+str(value['id']),'table_id':tid,'account':label['raw_value'],'period':period,'unit':anchor['unit'],'value':value['numeric_lexeme'],'source_id':value['source_id'],'cell':col+str(value['row_number']),'period_header':header,'unit_context':c.execute('SELECT raw_value FROM cells WHERE source_id=? AND column_name=? AND row_number=?',(loc['unit_source_id'],re.match('[A-Z]+',loc['unit_cell'])[0],int(re.search(r'\d+$',loc['unit_cell'])[0]))).fetchone()[0]}
                candidates.append(candidate)
                table['rows'].append([candidate['id'],candidate['account'],period,candidate['unit'],candidate['value']])
        table['pending_normalization_ids']=[x['id'] for x in candidates if x['table_id']==tid]
        source['text']=json.dumps(table,ensure_ascii=False,separators=(',',':'))
    c.close()
    if not candidates:raise ValueError('No missing income facts found; do not run redundant trial')
    payload=json.loads(request['messages'][-1]['content']);payload['compressed_sources']=evidence
    payload['supplemental_normalization_candidates']=candidates
    payload['review_focus']='추가 후보를 원문 좌표·기간 머리글·단위와 먼저 대조한다. approved인 경우에만 해석에 활용한다. 손익 흐름은 필요한 계정이 모두 있는 동일 income_statement 표를 우선 인용하면 basis 미확정이어도 표 내부 관계를 해석할 수 있다. 표 간 작성 기준 일치를 가정하는 것과 구분한다. 자본감소 원인을 다른 표 순손실로 확정하지 말고 자본변동 원인 미확인을 본문에 명시한다. 고정표와 기존 핵심 분석을 보존한다.'
    request['messages'][-1]['content']=json.dumps(payload,ensure_ascii=False)
    schema=request['structured_outputs']['json'];schema['properties']={'supplemental_normalization':{'type':'object','properties':{'decision':{'type':'string','enum':['approve','reject']},'issues':{'type':'array','items':{'type':'string'},'maxItems':5}},'required':['decision','issues'],'additionalProperties':False},**schema['properties']};schema['required']=['supplemental_normalization',*schema['required']]
    return request,evidence,candidates
