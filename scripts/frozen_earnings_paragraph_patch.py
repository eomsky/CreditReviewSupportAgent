"""C20.2: immediately materialize the earnings bridge into required prose."""
import ast

def patch(source):
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        properties=schema['properties']
        prose=copy.deepcopy(properties['analysis_paragraphs']['items'])
        properties['earnings_explanation_including_tax']=prose
        properties['earnings_highlight_including_tax']=copy.deepcopy(prose)
        schema['required']+=['earnings_explanation_including_tax','earnings_highlight_including_tax']
        order=['financing_support','earnings_bridge','earnings_explanation_including_tax','earnings_highlight_including_tax']
        schema['properties']={key:properties[key] for key in order if key in properties}
        schema['properties'].update({key:value for key,value in properties.items() if key not in order})
        schema['properties']['analysis_paragraphs']['maxItems']=4
        schema['properties']['paragraphs']['maxItems']=2
        messages[0]['content']+='\\n손익 상세문단과 특이사항은 각각 earnings_explanation_including_tax 및 earnings_highlight_including_tax에 필수 작성한다. 직전 earnings_bridge의 세전이익→법인세→순이익 연결을 확인하고 실제 원문 수치와 원인을 문장에 반영한다. 별도 analysis_paragraphs와 paragraphs에는 손익문단을 반복하지 말고 나머지 자산·자본·단기상환·전망 논점을 작성한다. 두 손익문단은 프로그램이 최종 본문과 특이사항에 함께 포함하므로 생략하거나 다른 배열에서 다시 요약할 필요가 없다.'
'''
    assert source.count(marker)==1
    source=source.replace(marker,extra+marker)
    marker="    result = app.json.loads(choice['message']['content'])"
    restore='''
    if 'earnings_explanation_including_tax' in result:
        result.setdefault('analysis_paragraphs',[]).append(result.pop('earnings_explanation_including_tax'))
        result.setdefault('paragraphs',[]).append(result.pop('earnings_highlight_including_tax'))
'''
    assert source.count(marker)==1
    source=source.replace(marker,marker+restore)
    ast.parse(source)
    return source
