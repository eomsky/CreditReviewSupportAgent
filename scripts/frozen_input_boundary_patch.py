"""Apply complete-excerpt input budgeting before every recovery attempt."""
import ast

HELPER='''
def split_budget_schema(schema):
    # A report may have a small document-review field and many large tables.
    # Split at table identity, not just the two unequal top-level fields.
    props=schema.get('properties',{})
    tables=props.get('planned_tables',{}).get('properties',{})
    if len(tables)>1:
        parts=[]
        for key,table in tables.items():
            part=copy.deepcopy(schema)
            container=copy.deepcopy(props['planned_tables'])
            container['properties']={key:copy.deepcopy(table)}
            container['required']=[key] if key in container.get('required',[]) else []
            part['properties']={'planned_tables':container}
            part['required']=['planned_tables'] if 'planned_tables' in schema.get('required',[]) else []
            parts.append(part)
        rest=[key for key in props if key!='planned_tables']
        if rest:
            part=copy.deepcopy(schema)
            part['properties']={key:copy.deepcopy(props[key]) for key in rest}
            part['required']=[key for key in schema.get('required',[]) if key in rest]
            parts.append(part)
        return parts
    return split_schema(schema)

'''

def patch(source):
    source='from frozen_input_boundary import fit as fit_input_boundary\n'+source
    source=source.replace('def complete(llm,',HELPER+'def complete(llm,',1)
    marker='    request=copy.deepcopy(payload);calls=0;events=[]'
    assert source.count(marker)==1
    source=source.replace(marker,marker+";preflight_audits=[];server_ceiling=None\n    original_token_count=token_count\n    def bounded_count(messages):\n        count,maximum=original_token_count(messages)\n        return count,min(maximum,server_ceiling) if server_ceiling is not None else maximum\n    token_count=bounded_count")
    source=source.replace('        nonlocal calls','        nonlocal calls,server_ceiling')
    marker="        count,maximum=token_count(req['messages'])\n"
    assert source.count(marker)==1
    source=source.replace(marker,"        req,boundary=fit_input_boundary(req,token_count)\n        preflight_audits.append(boundary)\n        if boundary['status']=='source_units_selected':notify('토큰 조정 중: 출력 예산 확보 후 원문 단위로 입력 선택')\n"+marker)
    start=source.index('        if available<1024:\n')
    end=source.index('        # Partition a large response',start)
    source=source[:start]+"        if available<1024:raise CapacityError('필수 근거와 검토 본문 자체가 입력 예산을 초과합니다. 원문을 절단하지 않고 해당 검토 단위를 분리해야 합니다.')\n"+source[end:]
    old="parts=split_schema(req['structured_outputs']['json']) if depth==0 and req['max_tokens']>available and available<4096 else None"
    assert source.count(old)==1
    source=source.replace(old,"parts=split_budget_schema(req['structured_outputs']['json']) if req['max_tokens']>available else None")
    old="child=copy.deepcopy(req);child['structured_outputs']['json']=part"
    assert source.count(old)==1
    source=source.replace(old,old+"\n                if 'planned_tables' in part.get('properties',{}):\n                    child['max_tokens']=max(1024,min(req['max_tokens'],available-128))\n                else:\n                    child['max_tokens']=min(available,max(1024,(req['max_tokens']+len(parts)-1)//len(parts)))")
    start=source.index('            req[\'max_tokens\']=max(512,req[\'max_tokens\']//2)')
    end=source.index('            return run(req,depth+1)',start)
    source=source[:start]+"            server_ceiling=max(2048,int(maximum*.8))\n            notify('토큰 조정 중: 서버 한도에 맞춰 원문 단위 재선택')\n"+source[end:]
    marker='    if events:result[\'recovery\']=events'
    assert source.count(marker)==1
    source=source.replace(marker,marker+"\n    result['input_boundary_audits']=preflight_audits")
    ast.parse(source)
    return source
