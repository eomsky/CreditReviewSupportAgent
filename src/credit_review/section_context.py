"""Attach preceding structural headings to titleless table chunks.

Uses extracted positions, not page-opening guesses. Original artifacts and
numeric bodies remain unchanged; the derived link records its heading source.
"""
from bisect import bisect_right
from collections import defaultdict
import re


def position(source, end=False):
    located=source.metadata.get('structured',{}).get('source',{})
    boxes=located.get('bboxes') or []
    pages=located.get('pages') or []
    if not boxes or not pages:
        return None
    page=pages[0]
    if len(set(pages))!=1:
        physical=re.fullmatch(r'P(\d+)_T\d+',source.metadata.get('physical_table_id',''))
        if source.kind!='table' or not physical or int(physical[1]) not in pages:
            return None
        page=int(physical[1])
    return (page, max(box[3] for box in boxes) if end else min(box[1] for box in boxes))


def attach_section_context(sources):
    headings=defaultdict(list)
    first_parts={}
    for source in sources.values():
        structure=source.metadata.get('structured',{})
        path=structure.get('section_path') or []
        start=position(source)
        if source.kind=='table' and start:
            logical=source.metadata.get('logical_table_id')
            if logical:
                key=(source.document_id,logical)
                first_parts[key]=min(first_parts.get(key,start),start)
        elif path and position(source,end=True):
            headings[source.document_id].append((position(source,end=True),source.id,path))
    for rows in headings.values(): rows.sort(key=lambda row:row[0])
    result=dict(sources)
    for sid,source in sources.items():
        structure=source.metadata.get('structured',{})
        if source.kind!='table' or structure.get('section_path'):
            continue
        start=position(source)
        if start is None: continue
        logical=source.metadata.get('logical_table_id')
        start=first_parts.get((source.document_id,logical),start)
        rows=headings.get(source.document_id,[])
        index=bisect_right([row[0] for row in rows],start)-1
        if index<0: continue
        where,anchor,path=rows[index]
        metadata={**source.metadata,
                  'section_context':{'source_id':anchor,'position':list(where),
                                     'method':'preceding_structural_heading'},
                  'structured':{**structure,'section_path':list(path)}}
        result[sid]=source.model_copy(update={'metadata':metadata})
    return attach_financial_regions(result)


def attach_financial_regions(sources):
    """Keep the explicit statement-section scope through nested note headings.

    Some DART note headings replace their parent's section_path. A coordinate
    interval anchored to the actual statement heading restores that parent;
    it never infers scope from financial amounts or neighboring page openings.
    """
    markers=defaultdict(list)
    for source in sources.values():
        if source.kind=='table': continue
        path=source.metadata.get('structured',{}).get('section_path') or []
        where=position(source,end=True)
        if not path or where is None: continue
        financial=any('재무에 관한 사항' in str(t) for t in path)
        scope=None; boundary=not financial
        if financial:
            for title in path:
                title=re.sub(r'\s+','',str(title))
                if re.fullmatch(r'\d+\.(?:연결)재무제표(?:주석)?',title):
                    scope='CONSOLIDATED'; boundary=True
                elif re.fullmatch(r'\d+\.(?:별도|개별)?재무제표(?:주석)?',title):
                    scope='SEPARATE'; boundary=True
                elif re.match(r'\d+\.(?:배당에관한사항|증권의발행|기타재무에관한사항)',title):
                    scope=None; boundary=True
        if boundary:
            markers[source.document_id].append((where,source.id,scope,path))
    for rows in markers.values(): rows.sort(key=lambda row:row[0])
    result=dict(sources)
    for sid,source in sources.items():
        where=position(source)
        rows=markers.get(source.document_id,[])
        if where is None or not rows: continue
        index=bisect_right([row[0] for row in rows],where)-1
        if index<0 or rows[index][2] is None: continue
        start,anchor,scope,path=rows[index]
        metadata={**source.metadata,'financial_section_scope':{
            'scope':scope,'source_id':anchor,'position':list(start),
            'section_path':list(path),'method':'explicit_statement_section_interval'}}
        result[sid]=source.model_copy(update={'metadata':metadata})
    return result
