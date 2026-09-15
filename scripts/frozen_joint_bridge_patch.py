"""C14: require a compact earnings bridge in the same generation response."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    assert source.count(marker)==1
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        bridge={'type':'object','properties':{
            'period':{'type':'string'},
            'pretax_profit':{'type':['number','null']},
            'income_tax':{'type':['number','null']},
            'net_profit':{'type':['number','null']},
            'unit':{'type':'string'},
            'source_ids':{'type':'array','items':{'type':'string','enum':list(aliases)}}},
            'required':['period','pretax_profit','income_tax','net_profit','unit','source_ids'],
            'additionalProperties':False}
        schema['properties']={'earnings_bridge':bridge,**schema['properties']}
        schema['required']=['earnings_bridge']+schema['required']
        schema['properties']['analysis_paragraphs']['maxItems']=4
        messages[0]['content']+='\\nearnings_bridge를 먼저 원문에서 채운다. 최신 실적의 같은 기준 세전이익·법인세·순이익을 동일 단위로 기록하고 미확인은 null로 둔다. 세전 흑자·세후 적자이면 본문과 특이사항 모두 법인세 영향을 누락하지 않는다. 영업외비용 전체를 순손실과 동일시하지 않는다. 분석의견은 주요 자산·운전자산 변화, 차입 및 자본구조, 손익 연결, 추정 전망의 논점을 최대4문단에 통합한다. 같은 수치와 결론은 반복하지 않되 원인·조건·중요정보를 생략하지 않는다.'
'''
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
