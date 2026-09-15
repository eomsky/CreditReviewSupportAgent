"""C20: preserve balance-sheet and near-term repayment analysis."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    assert source.count(marker)==1
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        schema['properties']['analysis_paragraphs']['maxItems']=5
        messages[0]['content']+='\\n분석 논점 보존을 위해 상세문단은 최대5개로 허용한다. 자산·운전자산, 차입과 자본, 단기상환부담, 손익연결, 전망 중 중요한 논점을 누락하지 않는다. 부채비율=부채/자본이며 자산 증가 자체는 부채비율 상승의 원인이 아니다. 비율 변동 원인을 설명할 때 분자와 분모의 변동을 확인한다. 단기차입 증가와 자본 감소가 원문에 있으면 각각 상환시기 부담과 손실흡수력 관점에서 설명한다. 같은 수치는 중복하지 않는다.'
'''
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
