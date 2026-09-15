"""C19: require original support before asserting financing purpose."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    assert source.count(marker)==1
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        support={'type':'object','properties':{
            'explicit_financing_purpose_quote':{'type':['string','null']},
            'source_ids':{'type':'array','items':{'type':'string','enum':list(aliases)}}},
            'required':['explicit_financing_purpose_quote','source_ids'],'additionalProperties':False}
        schema['properties']={'financing_support':support,**schema['properties']}
        schema['required']=['financing_support']+schema['required']
        messages[0]['content']+='\\nfinancing_support에는 자금조달 용도가 직접 명시된 원문 구절만 기록한다. 자산과 차입 잔액이 함께 증가한 표는 용도의 증거가 아니므로 그 경우 quote는 null이다. quote가 null이면 본문에서도 취득을 위한 조달·투자자금 차입처럼 용도를 확정하지 말고 동시 증가와 상환 부담만 분석한다. 부채비율은 부채와 자본 모두에 의해 변하므로 차입 증가를 유일한 원인으로 쓰지 말고 자본 변동도 검토한다. 이 필드는 사실 검토 보조이며 자체 품질 통과가 아니다.'
'''
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
