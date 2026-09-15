"""Attach preceding spreadsheet unit/period context using actual header rows."""
import re


def unit_rows(source):
    result=[]
    for line in source.get('text','').splitlines():
        if not re.search(r'단위\s*[:：]',line):continue
        cell=re.search(r'[A-Z]{1,3}(\d+)=',line)
        if cell:result.append(int(cell[1]))
    return result


def ensure_headers(store,sources,manifest):
    result={s['id']:s for s in sources}
    metadata={m['id']:m for m in manifest}
    for source in sources:
        if source.get('sheet') is None:continue
        first=re.search(r'[A-Z]{1,3}(\d+)=',source['text'])
        if not first:continue
        candidates=[]
        for header in store.get(source['document_id'])['sources']:
            if header.get('sheet')!=source['sheet'] or header['id']==source['id']:continue
            if not re.search(r'20\d{2}',header['text']):continue
            preceding=[r for r in unit_rows(header) if r<=int(first[1])]
            if preceding:candidates.append((max(preceding),header))
        if candidates:
            _,header=max(candidates,key=lambda item:item[0])
            result.setdefault(header['id'],{**header,'metadata':metadata[source['document_id']],'table_coverage':True,'retrieval_mode':'preceding_unit_header'})
    return list(result.values())
