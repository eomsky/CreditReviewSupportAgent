"""Scope a fully source-authored financial view to its original document."""
import copy
from frozen_exact_template_source import bind_templates


def primary_ids(templates,evidence,priorities):
    bound=bind_templates(evidence,templates,priorities)
    if len(bound)!=len(templates) or not bound:return set()
    ids={record['source_document_id'] for record in bound.values()}
    return ids if len(ids)==1 else set()


def scoped(view,evidence,manifest):
    import fixed_review_tables
    from review_documents import PRIORITIES
    templates=fixed_review_tables.TEMPLATES.get(view)
    if not templates:return evidence,manifest
    ids=primary_ids(templates,evidence,PRIORITIES)
    if not ids:return evidence,manifest
    return [s for s in evidence if s['document_id'] in ids],[m for m in manifest if m['id'] in ids]


def scope_memory(view,memory):
    evidence,manifest=scoped(view,memory['evidence'],memory['documents'])
    if len(evidence)==len(memory['evidence']):return memory
    result=copy.deepcopy(memory)
    result['evidence']=evidence;result['documents']=manifest
    ids={s['id'] for s in evidence}
    result['compressed_sources']=[s for s in result['compressed_sources'] if s['id'] in ids]
    # The generation packet already used this same scope. If applying to an
    # older unspecialized draft, force a fresh claim check instead of stale aliases.
    packet=result.get('prepared_context') or result['draft'].get('evidence_assessment',{})
    records=packet.get('facts',[])+packet.get('numeric_evidence',[])
    if any(not set(r['source_ids'])<=ids for r in records):
        result.pop('prepared_context',None);result['draft'].pop('evidence_assessment',None)
    return result
