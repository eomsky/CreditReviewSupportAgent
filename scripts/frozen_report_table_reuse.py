"""Candidate: reuse source-authored table projections only on exact coordinates."""
import copy,re,json


def normalized(value):return re.sub(r'\s+','',str(value))


def bind(packet,prior,evidence):
    source_map={s['id']:s for s in evidence}
    originals=[]
    for view,section in prior.items():
        if not section.get('refinement'):continue
        for ti,table in enumerate(section.get('tables',[])):
            binding=table.get('source_binding',{})
            if binding.get('method')!='exact_source_template' or not binding.get('source_id'):continue
            unit=re.search(r'단위\s*[:：]\s*([^)]*)',table.get('caption',''))
            if not unit:continue
            originals.append((view,ti,table,binding,unit[1].strip()))
    result={}
    for pi,plan in enumerate(packet.get('tables',[])):
        possibilities=[]
        plan_sources=plan.get('source_ids',[])
        for view,ti,table,binding,unit in originals:
            if binding['source_id'] not in plan_sources:continue
            # A plan mixing documents may intend a different accounting scope.
            if any(sid not in source_map or source_map[sid]['document_id']!=binding.get('document_id') for sid in plan_sources):continue
            caption_unit=re.search(r'단위\s*[:：]\s*([^)]*)',plan.get('caption',''))
            if caption_unit and normalized(caption_unit[1])!=normalized(unit):continue
            columns=table['columns'];rows=table['rows']
            column_names=[normalized(c) for c in columns]
            row_names=[normalized(r[0]) for r in rows]
            targets=[normalized(c) for c in plan['columns'][1:]]
            row_targets=[normalized(r) for r in plan['rows']]
            if not targets or not row_targets:continue
            if any(column_names.count(c)!=1 for c in targets) or any(row_names.count(r)!=1 for r in row_targets):continue
            ci=[column_names.index(c) for c in targets]
            if 0 in ci:continue
            ri=[row_names.index(r) for r in row_targets]
            values=[[plan['rows'][i]]+[copy.deepcopy(rows[r][c]) for c in ci] for i,r in enumerate(ri)]
            possibilities.append({'columns':copy.deepcopy(plan['columns']),'rows':values,'unit':unit,
                'source_ids':[binding['source_id']],'source_binding':{**copy.deepcopy(binding),'projection':{'view':view,'table':ti,'rows':ri,'columns':[0]+ci}}})
        if possibilities:
            fingerprints={json.dumps([p['columns'],p['rows'],p['unit']],ensure_ascii=False,sort_keys=True) for p in possibilities}
            if len(fingerprints)==1:result[f'T{pi}']=possibilities[0]
    return result


def configure(schema,bindings):
    for key in bindings:
        spec=schema['properties']['planned_tables']['properties'][key]
        del spec['properties']['rows']
        spec['required'].remove('rows')


def restore(result,bindings,aliases):
    reverse={s['id']:key for key,s in aliases.items()}
    for key,binding in bindings.items():
        value=result['planned_tables'][key]
        value['source_ids']=[reverse[sid] for sid in binding['source_ids']]
        value['unit']=binding['unit']
        value['rows']={f'R{i}':{f'C{ci}':copy.deepcopy(row[ci]) for ci in range(1,len(row))} for i,row in enumerate(binding['rows'])}


def annotate(result,packet,bindings):
    positions={}
    for i,plan in enumerate(packet['tables']):
        section=next(s for s in result['sections'] if s['title']==plan['section'])
        position=positions.get(plan['section'],0);positions[plan['section']]=position+1
        if f'T{i}' in bindings:
            table=section['tables'][position]
            binding=bindings[f'T{i}']
            if table['rows']!=binding['rows'] or table['columns']!=binding['columns']:raise ValueError('재사용 표 좌표 불일치')
            table['source_binding']=copy.deepcopy(binding['source_binding'])
            table['value_origin']='source_authored_projection'
