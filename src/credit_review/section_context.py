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
    return result
