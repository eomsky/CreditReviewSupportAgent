"""Bound internal audit explanations, never report/body paragraphs."""
import ast

def patch(source):
    old="    check['required'].remove('category')"
    assert source.count(old)==1
    source=source.replace(old,old+"\n    check['properties']['reason'].update(maxLength=400,description='핵심 대조 결과만 1~3문장으로 기록. 수치 목록이나 같은 결론을 반복하지 않는다. 상세한 설명은 수정 본문에 작성한다.')")
    ast.parse(source)
    return source
