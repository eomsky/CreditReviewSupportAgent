"""Identify a complete source-authored fixed table; never guess columns or units."""
import re
from decimal import Decimal


def normalized(text):
    return re.sub(r'\s+', '', text)


def cell_values(line):
    # Native spreadsheet addresses carry provenance, not financial values.
    return [re.sub(r'^[A-Z]+\d+=', '', part.strip()) for part in line.split('|')]


def exact_table(source, template):
    if source.get('format') not in ('xls','xlsx') or template.get('customer'):
        return None
    lines = source['text'].splitlines()
    starts = [i for i,line in enumerate(lines) if normalized(cell_values(line)[0]) == normalized(template['caption'])]
    found=[]
    for start in starts:
        rows=[cell_values(line) for line in lines[start+1:] if line.strip()]
        if not rows:continue
        header=rows[0]
        width=len(template['columns'])
        if len(header)!=width or len(rows)<len(template['labels'])+1:continue
        if not all(re.fullmatch(r'20\d{2}(?:-\d{2})?', period) for period in header[1:4]):continue
        if header[1:4]!=sorted(set(header[1:4])):continue
        if list(map(normalized,header[4:]))!=list(map(normalized,template['columns'][4:])):continue
        values=[];valid=True
        for label,row in zip(template['labels'],rows[1:]):
            if len(row)!=width or normalized(row[0])!=normalized(label):valid=False;break
            converted=[]
            for raw in row[1:]:
                if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',raw):valid=False;break
                amount=Decimal(raw)
                # -1 can be a missing marker; require semantic resolution instead.
                if amount==-1:valid=False;break
                converted.append(int(amount) if amount==amount.to_integral_value() else float(amount))
            if not valid:break
            values.append(converted)
        if valid:
            found.append({'periods':header[1:4],**{f'r{i}':r for i,r in enumerate(values)},
                          'source_id':source['id'],'source_document_id':source['document_id'],
                          'semantic_review_required':True})
    return found[0] if len(found)==1 else None


def bind_templates(evidence, templates, priorities):
    bound = {}
    for index,template in enumerate(templates):
        candidates=[]
        for source in evidence:
            result=exact_table(source,template)
            if result:
                rank=priorities.get(source.get('metadata',{}).get('priority'),0)
                candidates.append((rank,result))
        if not candidates:continue
        best=max(rank for rank,_ in candidates)
        winners=[result for rank,result in candidates if rank==best]
        # Priority ranks relevance, not the truth of conflicting accounting data.
        values=[{k:v for k,v in result.items() if k=='periods' or re.fullmatch(r'r\d+',k)} for _,result in candidates]
        if any(value!=values[0] for value in values[1:]):continue
        bound[f't{index}']=winners[0]
    return bound


def restore_bound(result, bound):
    for key,table in bound.items():
        result.setdefault('fixed_tables',{})[key]={k:v for k,v in table.items() if k=='periods' or re.fullmatch(r'r\d+',k)}


def ensure_exact_sources(store, templates, manifest, evidence, priorities):
    candidates=[]
    for meta in manifest:
        doc=store.get(meta['id'])
        if doc.get('format') not in ('xls','xlsx'):continue
        candidates.extend({**s,'metadata':meta,'document_name':meta['name']} for s in doc['sources'])
    bound=bind_templates(candidates,templates,priorities)
    ids={t['source_id'] for t in bound.values()}
    result={s['id']:s for s in evidence}
    for source in candidates:
        if source['id'] in ids:
            result[source['id']]={**source,'table_coverage':True,'retrieval_mode':'exact_template'}
    return list(result.values())
