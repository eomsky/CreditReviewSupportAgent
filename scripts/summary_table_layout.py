"""Reversible single-record layout for flexible summary tables only."""
import copy
def improve(tables):
 audit=[]
 for index,t in enumerate(tables):
  cols=t.get('columns',[]);rows=t.get('rows',[])
  if t.get('fixed_template') or len(cols)<7 or len(rows)!=1 or len(rows[0])!=len(cols):continue
  original=copy.deepcopy(t)
  t['columns']=['항목','내용'];t['rows']=[[k,v] for k,v in zip(cols,rows[0])];t['column_widths']=[40,60]
  audit.append({'table_index':index,'original':original,'layout':'single_record_vertical','values_preserved':True})
 return audit
