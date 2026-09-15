"""Prepare provenance-bound monetary auxiliary facts; unresolved headers fail closed."""
import sqlite3,json,re,time,argparse
from pathlib import Path
from decimal import Decimal
root=Path(__file__).resolve().parents[1];folder=root/'outputs/step_trials/C20.4s'
parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,default=folder);args=parser.parse_args();folder=args.folder
c=sqlite3.connect(folder/'numeric.sqlite');c.row_factory=sqlite3.Row
wanted={'법인세차감전계속영업이익(손실)','계속영업법인세(부의법인세)','당기순이익(손실)','영업외수익','영업외비용','유동차입부채','건물','부채총계','자산총계'}
allcells=[dict(r) for r in c.execute('SELECT cells.*,sources.sheet FROM cells JOIN sources ON cells.source_id=sources.id ORDER BY sources.sheet,row_number,cells.id')]
rows={}
for cell in allcells:rows.setdefault((cell['sheet'],cell['row_number']),[]).append(cell)
groups=[]
for (sheet,row),cells in rows.items():
    label=cells[0]['raw_value']
    if label not in wanted:continue
    candidates=[]
    for (sh,rn),hc in rows.items():
        if sh!=sheet or rn>=row:continue
        periods={x['column_name']:(x,re.match(r'^(20[0-9]{2}-[0-9]{2})(?:\s|$)',x['raw_value'])) for x in hc}
        periods={col:(x,m[1]) for col,(x,m) in periods.items() if m}
        if len(periods)>=2:candidates.append((rn,periods))
    if not candidates:continue
    header_row,headers=max(candidates,key=lambda x:x[0])
    units=[x for x in allcells if x['sheet']==sheet and x['row_number']<header_row and re.search(r'단위\s*:\s*백만원',x['raw_value'])]
    if not units:continue
    unit_cell=max(units,key=lambda x:x['row_number'])
    # A later unit declaration prevents borrowing an unrelated monetary header.
    later=[x for x in allcells if x['sheet']==sheet and unit_cell['row_number']<x['row_number']<header_row and '단위' in x['raw_value']]
    if later:continue
    fs=[]
    for cell in cells:
        if cell['column_name'] not in headers or cell['numeric_lexeme'] is None:continue
        if c.execute('SELECT 1 FROM facts WHERE cell_id=?',(cell['id'],)).fetchone():continue
        h,period=headers[cell['column_name']]
        loc={'source_id':cell['source_id'],'cell':cell['column_name']+str(row),'period_source_id':h['source_id'],'period_cell':h['column_name']+str(header_row),'unit_source_id':unit_cell['source_id'],'unit_cell':unit_cell['column_name']+str(unit_cell['row_number'])}
        value=str(Decimal(cell['numeric_lexeme']));cur=c.execute('INSERT INTO facts(cell_id,account,period,unit,value_decimal,review_evidence) VALUES (?,?,?,?,?,?)',(cell['id'],label,period,'백만원',value,json.dumps(loc,ensure_ascii=False)))
        fs.append({'id':cur.lastrowid,'account':label,'period':period,'unit':'백만원','value':value,'locator':loc})
    if fs:groups.append({'sheet':sheet,'unit_header':unit_cell['raw_value'],'period_header':' | '.join(x['column_name']+str(header_row)+'='+x['raw_value'] for x,_ in headers.values()),'original_row':' | '.join(x['column_name']+str(row)+'='+x['raw_value'] for x in cells),'facts':fs})
c.commit();c.close()
request=json.loads((folder/'normalization.request.json').read_text());request['messages'][1]['content']=json.dumps(groups,ensure_ascii=False);request['messages'][0]['content']+=' 期間欄の構成比は金額ではない。'.replace(' 期間欄の構成比は金額ではない。',' 기간 사이 구성비 열은 금액 열과 구분한다. 머리글이 다른 원문 조각이어도 같은 시트의 원문 좌표로 대조한다.')
(folder/'auxiliary.request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8');(folder/'auxiliary-candidates.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2),encoding='utf-8')
print({'groups':len(groups),'facts':sum(len(g['facts']) for g in groups)})
