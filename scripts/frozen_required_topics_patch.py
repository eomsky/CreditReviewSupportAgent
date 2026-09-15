"""C20.4: require all analytical topics without additional model calls."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        paragraph_item=copy.deepcopy(schema['properties']['analysis_paragraphs']['items'])
        topics=['sales_working_capital','assets_and_financing','capital_and_short_term_repayment','forecast_and_conditions']
        schema['properties']['analysis_paragraphs']={'type':'object','properties':{key:copy.deepcopy(paragraph_item) for key in topics},'required':topics,'additionalProperties':False}
        messages[0]['content']+='\\nanalysis_paragraphs는 배열 대신 지정된 네 논점의 객체로 작성한다. sales_working_capital=매출 및 운전자산, assets_and_financing=자산과 차입변동/근거가 있는 조달용도, capital_and_short_term_repayment=자본변동과 단기상환부담, forecast_and_conditions=추정 실적·금융비용·상환조건. 제공된 자료가 있는 논점을 누락하지 않는다. earnings_explanation_including_tax는 세전·법인세·순손익 연결과 함께 영업성과와 영업외손익 변화를 분석한다. 각 필드에는 해당 원문근거를 붙이며 예시수치를 쓰지 않는다.'
'''
    assert source.count(marker)==1
    source=source.replace(marker,extra+marker)
    marker="    result = app.json.loads(choice['message']['content'])"
    extra='''
    if isinstance(result.get('analysis_paragraphs'),dict):
        result['analysis_paragraphs']=[result['analysis_paragraphs'][key] for key in ['sales_working_capital','assets_and_financing','capital_and_short_term_repayment','forecast_and_conditions']]
'''
    assert source.count(marker)==1
    source=source.replace(marker,marker+extra)
    ast.parse(source)
    return source
