"""C15: explicit comparison intervals and concise non-repeated synthesis."""
import ast

def patch(source):
    marker="        schema['properties']['analysis_paragraphs']['maxItems']=4"
    assert source.count(marker)==1
    addition='''
        for field,limit in [('paragraphs',160),('analysis_paragraphs',200)]:
            schema['properties'][field]['items']=copy.deepcopy(schema['properties'][field]['items'])
            schema['properties'][field]['items']['properties']['text']['maxLength']=limit
        messages[0]['content']+='\\n증가액마다 비교 시작·종료 기간을 명시한다. 원문의 증감 열은 그 표의 전기 대비 당기이며, 2년 누적 증가액의 구성으로 1년 증감을 제시하지 않는다. 세부 항목과 총액의 정의나 기간이 다르면 인과 구성으로 연결하지 말고 별개 추세로 설명한다. 회전기간 단축만으로 회수 건전성을 확정하지 않는다. 특이사항은 상세본문 반복 대신 핵심 판단을 간결하게 쓰고, 상세문단은 기존 논점을 유지하면서 중복 숫자·접속어를 줄인다.'
'''
    source=source.replace(marker,marker+addition)
    ast.parse(source)
    return source
