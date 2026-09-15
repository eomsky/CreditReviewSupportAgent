"""Copy exact source-authored tables, retain model review and other table paths."""
import ast


def patch(source):
    marker="    if fixed:\n        prompt+=fixed_review_tables.configure(schema,name)"
    replacement="""    bound_source_tables={}
    if fixed:
        prompt+=fixed_review_tables.configure(schema,name)
        from frozen_exact_template_source import bind_templates
        from review_documents import PRIORITIES
        bound_source_tables=bind_templates(evidence,fixed_review_tables.TEMPLATES[name],PRIORITIES)
        fixed_schema=schema['properties']['fixed_tables']
        for key in bound_source_tables:
            del fixed_schema['properties'][key]
            fixed_schema['required'].remove(key)
        if not fixed_schema['properties']:
            del schema['properties']['fixed_tables']
            schema['required'].remove('fixed_tables')
        if bound_source_tables:
            prompt+='\\n원문과 제목·단위·행·열·기간이 정확히 일치한 source_authored_fixed_tables는 아래 원문 값 그대로 프로그램이 표시한다. 이 표를 응답에 다시 작성하지 않는다. 본문은 이 표의 동일 기준 수치와 sources를 대조한다. 의미·기준의 적정성은 후속 검토 대상이며 해당 표만으로 다른 연결/별도 기준을 추정하지 않는다. 스키마에 남은 표만 직접 작성한다.\\nsource_authored_fixed_tables='+app.json.dumps(bound_source_tables,ensure_ascii=False)
"""
    assert source.count(marker)==1
    source=source.replace(marker,replacement)
    marker="    evidence.sort(key=lambda s:s['id'] not in planned_ids)"
    assert source.count(marker)==1
    source=source.replace(marker,"    planned_ids|={table['source_id'] for table in bound_source_tables.values()}\n"+marker)
    marker='    if fixed:fixed_review_tables.apply(result,name)'
    assert source.count(marker)==1
    source=source.replace(marker,"    if fixed:\n        from frozen_exact_template_source import restore_bound\n        restore_bound(result,bound_source_tables)\n        fixed_review_tables.apply(result,name)\n        for key,binding in bound_source_tables.items():\n            result['tables'][int(key[1:])]['source_binding']={'source_id':binding['source_id'],'document_id':binding['source_document_id'],'method':'exact_source_template','semantic_review_required':True}")
    ast.parse(source)
    return source
