import ast


def patch(source):
    source=source.replace('def select_sources(view, manifest=None):','def _before_primary_sources(view, manifest=None):')
    marker='def token_count(messages):'
    wrapper="""def select_sources(view, manifest=None):
    manifest=manifest or STORE.manifest([{'id':DOC_ID,'priority':'중요','required':True}])
    templates=fixed_review_tables.TEMPLATES.get(view)
    if templates:
        from frozen_exact_template_source import ensure_exact_sources
        from frozen_primary_scope import primary_ids
        from review_documents import PRIORITIES
        originals=ensure_exact_sources(STORE,templates,manifest,[],PRIORITIES)
        ids=primary_ids(templates,originals,PRIORITIES)
        if ids:manifest=[m for m in manifest if m['id'] in ids]
    rows=_before_primary_sources(view,manifest)
    if view in ('financial_accounts','profitability'):
        bridge=STORE.select(['법인세차감전','법인세비용','당기순손익'],manifest,budget=6000,limit=1)
        from frozen_source_headers import ensure_headers
        bridge=ensure_headers(STORE,bridge,manifest)
        rows=list({s['id']:s for s in rows+bridge}.values())
    return rows


"""
    assert source.count(marker)==1
    source=source.replace(marker,wrapper+marker)
    marker='    stage=(state.get(\'run\') or {}).get(\'stage\',name) if state else name'
    assert source.count(marker)==1
    source=source.replace(marker,"    from frozen_primary_scope import scoped\n    evidence,manifest=scoped(name,evidence,manifest)\n    if manifest and name in fixed_review_tables.TEMPLATES:\n        prompt+='\\n이번 고정표 분석의 자료 범위: '+', '.join(m['name'] for m in manifest)+'. 이 범위의 수치와 기간으로 비교한다. 다른 문서·연결범위의 종합 검토는 종합의견2 및 보고서에서 별도로 수행한다.'\n"+marker)
    marker="            memory=review_refinement.prepare_memory(app,llm_stream,token_count,folder,key,memory,memory['prompt'],state,cancel_event)"
    assert source.count(marker)==1
    source=source.replace(marker,"            from frozen_primary_scope import scope_memory\n            memory=scope_memory(key,memory)\n"+marker)
    ast.parse(source)
    return source
