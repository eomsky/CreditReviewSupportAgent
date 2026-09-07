"""Explicit statement labels outrank neighboring page headings, never amounts."""
import json
import re


def _labels(text):
    text=re.sub(r'\s+','',text)
    result=set()
    statement=r'(?:재무|포괄손익|손익계산|현금흐름|자본변동)'
    for marker,scope in [('연결','CONSOLIDATED'),('별도','SEPARATE'),('개별','SEPARATE')]:
        if re.search(marker+statement,text) or re.search(statement+r'[^\n]{0,15}[（(]'+marker+r'[）)]',text):
            result.add(scope)
    return result


def explicit_scope(source):
    structured=source.get('metadata',{}).get('structured') or {}
    tables=[x for x in structured.get('elements',[]) if x.get('type')=='table']
    card=source.get('table_index') or {}
    if not tables: tables=card.get('tables',[])
    titles=[x.get('title') for x in tables if x.get('title')]
    scopes=set().union(*(_labels(t) for t in titles)) if titles else set()
    basis=titles
    if not scopes:
        path=structured.get('section_path') or card.get('section_path') or []
        basis=[json.dumps(path,ensure_ascii=False)] if path else []
        scopes=set().union(*(_labels(t) for t in basis)) if basis else set()
    return {'scope':next(iter(scopes)) if len(scopes)==1 else 'CONFLICT' if scopes else 'UNKNOWN',
            'basis':basis if scopes else [],'method':'explicit_table_title_or_section'}


def validate_source_scopes(data,sources):
    refs={sid for row in data.cell_sources for ids in row.values() for sid in ids}
    labelled={sid:explicit_scope(sources[sid])['scope'] for sid in refs if sid in sources}
    known={scope for scope in labelled.values() if scope!='UNKNOWN'}
    if 'CONFLICT' in known or len(known)>1:
        raise ValueError('Dataset mixes explicitly labelled financial statement scopes: '+str(labelled))
    if data.scope!='UNKNOWN' and known and data.scope not in known:
        raise ValueError('Dataset scope '+data.scope+' conflicts with source table labels: '+str(labelled))
