"""C17: derive the short highlights after detailed analysis in one response."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    assert source.count(marker)==1
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        fields=schema['properties']
        order=['earnings_bridge','title','analysis_paragraphs','paragraphs']
        schema['properties']={key:fields[key] for key in order if key in fields}
        schema['properties'].update({key:value for key,value in fields.items() if key not in order})
        messages[0]['content']+='\\n상세 analysis_paragraphs를 먼저 작성한 후 paragraphs 특이사항을 요약한다. 특이사항은 확정된 주요 변화만 간단히 요약하고 원인 분석은 상세본문에서 설명한다. 요약에서 본문에 없는 원인을 추가하거나 복합 원인을 하나로 바꾸지 않는다. 차입 규모뿐 아니라 단기 상환 부담과 자본 변동도 중요하면 상세 분석에 함께 반영한다. 자산 증가만으로 설비투자 집행이나 조달 용도를 확정하지 않는다.'
'''
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
