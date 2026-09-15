"""Add the nearest preceding header instead of every nearby header body."""
import ast


def patch(source):
    start=source.index('    # Include nearby table headers')
    end=source.index('    return list(found.values())',start)
    replacement='''    # Preserve closest preceding unit/year context, avoiding unrelated nearby tables.
    from frozen_source_headers import unit_rows
    for source in list(found.values()):
        candidates=[]
        for header in store.get(source['document_id'])['sources']:
            if not re.search(r'단위\\s*:',header['text']) or not re.search(r'20\\d{2}',header['text']):continue
            if source.get('page') is not None and header.get('page') is not None:
                distance=source['page']-header['page']
                sy=source.get('bbox',[0,0])[1];hy=header.get('bbox',[0,0])[1]
                if 0<=distance<=2 and (distance>0 or hy<=sy):candidates.append(((distance,-hy),header))
            elif source.get('sheet') is not None and header.get('sheet')==source['sheet']:
                srow=re.search(r'[A-Z]+(\\d+)=',source['text'])
                preceding=[r for r in unit_rows(header) if srow and r<=int(srow[1])]
                if preceding:candidates.append(((int(srow[1])-max(preceding),0),header))
        if candidates:
            _,header=min(candidates,key=lambda row:row[0])
            found.setdefault(header['id'],{**header,'metadata':source.get('metadata',{})})
'''
    result=source[:start]+replacement+source[end:]
    ast.parse(result)
    return result
