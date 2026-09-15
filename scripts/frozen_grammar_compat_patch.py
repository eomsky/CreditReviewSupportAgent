"""C16: preserve string patterns without unsupported length intersections."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    assert source.count(marker)==1
    extra='''    def compatible_strings(node):
        if isinstance(node,dict):
            if 'pattern' in node and ('maxLength' in node or 'minLength' in node):
                node.pop('maxLength',None)
                node.pop('minLength',None)
            for item in node.values():compatible_strings(item)
        elif isinstance(node,list):
            for item in node:compatible_strings(item)
    compatible_strings(schema)
    if packet.get('preparation_mode')=='combined_with_generation':
        messages[0]['content']+='\\n중복 표현을 줄여 특이사항은 약160자, 상세분석 각 문단은 약200자 이내를 지향한다. 필수 근거와 판단 조건이 있으면 분량보다 정확성을 우선한다.'
'''
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
