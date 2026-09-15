"""Reserve complete authored fixed templates even when semantic search misses them."""
import ast


def patch(source):
    marker='def select_sources(view, manifest=None):'
    assert source.count(marker)==1
    source=source.replace(marker,'def _retrieved_sources(view, manifest=None):')
    marker='def token_count(messages):'
    wrapper='''def select_sources(view, manifest=None):
    manifest=manifest or STORE.manifest([{'id':DOC_ID,'priority':'중요','required':True}])
    rows=_retrieved_sources(view,manifest)
    templates=fixed_review_tables.TEMPLATES.get(view)
    if templates:
        from frozen_exact_template_source import ensure_exact_sources
        from review_documents import PRIORITIES
        rows=ensure_exact_sources(STORE,templates,manifest,rows,PRIORITIES)
    return rows


'''
    assert source.count(marker)==1
    source=source.replace(marker,wrapper+marker)
    ast.parse(source)
    return source
