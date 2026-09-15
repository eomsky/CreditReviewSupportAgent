"""Compact unchanged paragraph decisions without dropping paragraph coverage."""
import ast

def patch(source):
    marker="    report_table_review.add_schema(schema,draft,evidence)"
    assert source.count(marker)==1
    source=source.replace(marker,"""    edit=schema['properties']['revisions']['items']
    edit['properties']['action']={'type':'string','enum':['revise']}
    keep=obj({'paragraph_id':{'type':'string','enum':ids},'action':{'type':'string','enum':['keep']}})
    schema['properties']['revisions']['items']={'anyOf':[keep,edit]}
"""+marker)
    marker="    parsed=remap_ids(json.loads(choice['message']['content']),original_ids)"
    assert source.count(marker)==1
    source=source.replace(marker,marker+"""
    original_paragraphs={p['id']:p for section in sections(draft) for p in section['paragraphs']}
    for revision in parsed.get('revisions',[]):
        if revision['action']=='keep':
            paragraph=original_paragraphs[revision['paragraph_id']]
            revision.update(text='',reason='기존 문단 유지',source_ids=[s['id'] for s in paragraph.get('sources',[])])
""")
    marker="    system=with_reasoning(system)"
    assert source.count(marker)==1
    source=source.replace(marker,"    system+='\\n유지 판정 전송 규칙: revisions의 keep은 paragraph_id와 action만 반환한다. 원문 대조와 모든 문단의 판정 의무는 동일하며 기존 문단·출처는 프로그램이 그대로 유지한다. revise에는 기존처럼 수정된 전체 문단과 source_ids, reason을 작성한다. quality_checks에서 문제를 발견한 문단을 출력 절약을 위해 keep으로 두면 안 된다.'\n"+marker)
    ast.parse(source)
    return source
