"""Retain complete authored tables and remove identical customer display duplicates."""
import copy


def preserve(source,result):
    original=[t for s in source.get('sections',[source]) for t in s.get('tables',[])]
    tables=[t for s in result.get('sections',[result]) for t in s.get('tables',[])]
    for i,t in enumerate(tables):
        old=original[i] if i<len(original) else {}
        if old.get('source_binding',{}).get('method')=='exact_source_template':
            if t['rows']!=old['rows'] or t['columns']!=old['columns']:
                t.setdefault('source_conflicts',[]).append({'proposed_rows':copy.deepcopy(t['rows']),'proposed_columns':copy.deepcopy(t['columns']),'reason':'원문 완성표와 다른 검토값: 원문 값을 보존하고 기준 확인 필요'})
            for key in ('rows','columns','caption','source_binding'):t[key]=copy.deepcopy(old[key])
        for cell in old.get('materialized_cells',[]):
            ri=int(cell['row'][1:]);ci=int(cell['column'][1:])
            if t['columns']==old['columns'] and ri<len(t['rows']) and t['rows'][ri][0]==old['rows'][ri][0]:
                if t['rows'][ri][ci]!=cell['value']:
                    t.setdefault('source_conflicts',[]).append({'row':ri,'column':ci,'proposed_value':t['rows'][ri][ci],'reason':'원문에서 환산한 값 유지'})
                t['rows'][ri][ci]=cell['value']
        if len(t.get('columns',[]))==6 and len(t.get('rows',[]))>=2 and t['rows'][-1][0]=='합계' and t['rows'][-2][0]=='상기 외':
            for offset in (0,3):
                seen=set()
                for ri,row in enumerate(t['rows'][:-2]):
                    values=tuple(row[offset:offset+3])
                    if values[0] in (None,'','—'):continue
                    if values in seen:
                        row[offset:offset+3]=[None]*3
                        t.setdefault('duplicate_display_rows_removed',[]).append({'row':ri,'columns':[offset,offset+1,offset+2],'values':values})
                    else:seen.add(values)
    return result
