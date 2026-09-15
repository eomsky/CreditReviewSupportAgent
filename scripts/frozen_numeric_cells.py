"""Materialize monetary values from model-selected original text tokens."""
import re
from decimal import Decimal, ROUND_HALF_UP

SCALES={'원':Decimal(1),'천원':Decimal(1000),'백만원':Decimal(1000000),'억원':Decimal(100000000)}
NUMBER=re.compile(r'(?<![\w.])(?:\([+-]?\d[\d,]*(?:\.\d+)?\)|[+-]?\d[\d,]*(?:\.\d+)?)(?![\w.])')


def unit(text):
    labels=re.findall(r'단위\s*[:：]\s*([^\)\]\n]+)',text)
    return labels[0].strip() if len(labels)==1 and labels[0].strip() in SCALES else None


def eligible(table):
    return table.get('fixed_template') and not table.get('source_binding') and unit(table.get('caption','')) and not any('매출처' in str(c) for c in table['columns'])


def numbered(text):
    lines=[]
    for i,line in enumerate(text.splitlines()):
        counter=iter(range(10000))
        marked=NUMBER.sub(lambda m:f'[N{next(counter)}={m[0]}]',line)
        lines.append(f'L{i}: {marked}')
    return '\n'.join(lines)


def scoped_evidence(tables,evidence):
    if not tables or not all(eligible(t) for t in tables):return evidence
    chosen={}
    for table in tables:
        caption=re.sub(r'\([^)]*단위[^)]*\)','',table['caption'])
        title=re.sub(r'\s+','',caption)
        matches=[s for s in evidence if title and title in re.sub(r'\s+','',s['text'].splitlines()[0]) and s.get('page') and unit(s['text'])]
        if len(matches)!=1:return evidence
        header=matches[0]
        for s in evidence:
            if s['document_id']==header['document_id'] and s.get('page') and 0<=s['page']-header['page']<=1:
                chosen[s['id']]=s
    return list(chosen.values()) or evidence


def schema_cells(schema,tables,ids):
    for i,t in enumerate(tables):
        if not eligible(t):continue
        rows=schema['properties'][f'T{i}']['properties']['rows']['properties']
        for spec in rows.values():
            cells=spec['properties']['values']
            for key in list(cells['properties']):
                if key.startswith('C0:'):continue
                props={'source_id':{'type':'string','enum':ids},'line':{'type':'integer','minimum':0},'value_index':{'type':'integer','minimum':0},'header_source_id':{'type':'string','enum':ids},'period':{'type':'string'},'source_unit':{'type':'string','enum':list(SCALES)}}
                year=re.search(r'20\d{2}',key)
                if year:props['period']['enum']=[year[0]]
                cells['properties'][key]={'anyOf':[{'type':'null'},{'type':'object','properties':props,'required':list(props),'additionalProperties':False}]}
            cells['required']=[k for k in cells['properties'] if not k.startswith('C0:')]
    return schema


def period_position(ref,aliases):
    source=aliases[ref['source_id']];header=aliases[ref['header_source_id']]
    years=list(dict.fromkeys(re.findall(r'(?<!\d)20\d{2}(?!\d)',header['text'])))
    numbers=NUMBER.findall(source['text'].splitlines()[ref['line']])
    if len(years)!=len(numbers) or not years:return None
    return 0<=ref['value_index']<len(years) and years[ref['value_index']]==ref['period']


def original_period(ref,aliases):
    """Return a period only for an unambiguous original header/token alignment."""
    source=aliases[ref['source_id']];header=aliases[ref['header_source_id']]
    if source['document_id']!=header['document_id']:return None
    if source.get('page') and header.get('page') and not 0<=source['page']-header['page']<=2:return None
    years=list(dict.fromkeys(re.findall(r'(?<!\d)20\d{2}(?!\d)',header['text'])))
    numbers=NUMBER.findall(source['text'].splitlines()[ref['line']])
    if not years or len(years)!=len(numbers):return None
    index=ref['value_index']
    return years[index] if 0<=index<len(years) else None


def align_periods(candidate,aliases):
    """Resolve a redundant column address using the explicitly selected period.

    No value or period is inferred. Ambiguous targets and collisions are errors;
    the original header/unit/token validation still follows this transport step.
    """
    columns=candidate['columns'];moves=[]
    years={}
    for ci,label in enumerate(columns):
        match=re.search(r'20\d{2}',str(label))
        if ci and match:years.setdefault(match[0],[]).append(f'C{ci}')
    for row,record in candidate['rows'].items():
        values=record['values'];assigned={};origins={}
        for key,ref in values.items():
            if key=='C0' or ref is None:continue
            if not isinstance(ref,dict):raise ValueError('Numeric cell reference missing')
            supported=original_period(ref,aliases)
            if supported is not None and supported!=ref.get('period'):
                moves.append({'row':row,'from_period':ref.get('period'),'to_period':supported,
                              'reason':'original_header_token_position','source_id':ref['source_id'],
                              'line':ref['line'],'value_index':ref['value_index']})
                ref['period']=supported
            targets=years.get(ref.get('period'),[])
            if len(targets)!=1:raise ValueError('Numeric period has no unique target column')
            target=targets[0]
            if target!=key and period_position(ref,aliases) is not True:raise ValueError('Numeric coordinate repair lacks original period-position support')
            if target in assigned:raise ValueError('Conflicting references for the same numeric period')
            assigned[target]=ref;origins[target]=key
        remapped={key:(value if key=='C0' else None) for key,value in values.items()}
        remapped.update(assigned)
        record['values']=remapped
        for target,origin in origins.items():
            if target!=origin:moves.append({'row':row,'from':origin,'to':target,'period':assigned[target]['period']})
    return moves


def restore(result,tables,aliases):
    audit=[]
    for i,t in enumerate(tables):
        if not eligible(t):continue
        candidate=result[f'T{i}']; target=unit(t['caption'])
        moves=align_periods(candidate,aliases)
        if moves:t['numeric_coordinate_repairs']=moves
        for r,record in candidate['rows'].items():
            for key,ref in list(record['values'].items()):
                if key=='C0' or ref is None:continue
                if not isinstance(ref,dict):raise ValueError('Numeric cell reference missing')
                source=aliases[ref['source_id']];header=aliases[ref['header_source_id']]
                if source['document_id']!=header['document_id']:raise ValueError('Numeric header document mismatch')
                if source.get('page') and header.get('page') and not 0<=source['page']-header['page']<=2:raise ValueError('Numeric header outside local table context')
                declared=unit(header['text'])
                if declared!=ref['source_unit']:raise ValueError('Numeric unit not supported by original header')
                year=re.search(r'20\d{2}',str(candidate['columns'][int(key[1:])]))
                if not year or ref['period']!=year[0] or year[0] not in header['text']:raise ValueError('Numeric period not supported by original header')
                if period_position(ref,aliases) is False:raise ValueError('Numeric token does not match original period position')
                line=source['text'].splitlines()[ref['line']]
                raw=NUMBER.findall(line)[ref['value_index']]
                negative=raw.startswith('(')
                value=Decimal(raw.strip('()').replace(',',''))*(-1 if negative else 1)
                converted=value*SCALES[declared]/SCALES[target]
                rounded=converted.quantize(Decimal(1),rounding=ROUND_HALF_UP)
                record['values'][key]=int(rounded)
                audit.append({'table':i,'row':r,'column':key,'source_id':source['id'],'line':ref['line'],'raw':raw,'period':ref['period'],'source_unit':declared,'target_unit':target,'value':int(rounded),'semantic_review_required':True})
    for i,t in enumerate(tables):
        selected=[a for a in audit if a['table']==i]
        if selected:t['materialized_cells']=selected
    return audit
