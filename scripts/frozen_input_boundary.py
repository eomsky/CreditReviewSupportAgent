"""Select complete source excerpts before inference; never truncate text fields."""
import copy,json

def cited_ids(value):
    result=set()
    if isinstance(value,dict):
        for key,item in value.items():
            if key in ('source_id','header_source_id') and isinstance(item,str):result.add(item)
            elif key=='source_ids' and isinstance(item,list):result.update(v for v in item if isinstance(v,str))
            else:result.update(cited_ids(item))
    elif isinstance(value,list):
        for item in value:result.update(cited_ids(item))
    return result

def restrict_aliases(schema,available):
    if isinstance(schema,dict):
        props=schema.get('properties',{})
        for name in ('source_id','header_source_id','source_ids'):
            spec=props.get(name,{})
            if name=='source_ids':spec=spec.get('items',{})
            if 'enum' in spec:spec['enum']=[x for x in spec['enum'] if x in available]
        for item in schema.values():restrict_aliases(item,available)
    elif isinstance(schema,list):
        for item in schema:restrict_aliases(item,available)

def fit(request,token_count,reserve=None):
    candidate=copy.deepcopy(request)
    count,maximum=token_count(candidate['messages'])
    reserve=int(reserve if reserve is not None else candidate['max_tokens'])
    budget=maximum-reserve-512
    audit={'original_tokens':count,'maximum':maximum,'output_reserved':reserve,'input_ceiling':budget}
    if count<=budget:return candidate,{**audit,'input_tokens':count,'status':'within_budget','excluded_source_ids':[]}
    body=json.loads(candidate['messages'][-1]['content'])
    fields=[key for key in ('sources','compressed_sources') if isinstance(body.get(key),list)]
    sources={s['id']:s for key in fields for s in body[key]}
    # Prior model drafts are an optional writing aid, never original evidence.
    body.pop('prior_model_drafts',None)
    context={k:v for k,v in body.items() if k not in fields}
    protected=cited_ids(context)&sources.keys()
    for document in body.get('documents',[]):
        if not document.get('required'):continue
        rows=[s for s in sources.values() if s.get('document_id')==document['id']]
        if rows and not any(s['id'] in protected for s in rows):protected.add(rows[0]['id'])
    ordered=list(sources)
    # Retain the caller's semantic/vector relevance order. Do not use a company
    # name, numeric magnitude, or document priority to choose accounting truth.
    optional=[sid for sid in ordered if sid not in protected]
    def measure(n):
        keep=protected|set(optional[:n])
        # A selected excerpt may point at a separate period/unit header.
        # Keep explicit dependencies together, including transitive headers.
        while True:
            expanded=keep|{ref for sid in keep for ref in cited_ids(sources[sid]) if ref in sources}
            if expanded==keep:break
            keep=expanded
        selected=copy.deepcopy(body)
        for key in fields:selected[key]=[s for s in body[key] if s['id'] in keep]
        candidate['messages'][-1]['content']=json.dumps(selected,ensure_ascii=False,separators=(',',':'))
        measured,limit=token_count(candidate['messages'])
        return measured,limit,keep
    minimum,limit,keep=measure(0)
    if minimum>budget:
        # Return intact indispensable evidence so the caller can divide the
        # operation. Never silently cut a table, quote, or report paragraph.
        return candidate,{**audit,'input_tokens':minimum,'status':'indispensable_context_requires_partition','excluded_source_ids':[s for s in ordered if s not in keep]}
    low,high=0,len(optional)
    while low<high:
        mid=(low+high+1)//2
        if measure(mid)[0]<=budget:low=mid
        else:high=mid-1
    count,limit,keep=measure(low)
    while count>budget and low:
        low-=1;count,limit,keep=measure(low)
    if count>budget:raise ValueError('Input boundary did not converge')
    restrict_aliases(candidate.get('structured_outputs',{}).get('json',{}),keep)
    return candidate,{**audit,'input_tokens':count,'status':'source_units_selected','excluded_source_ids':[s for s in ordered if s not in keep]}
