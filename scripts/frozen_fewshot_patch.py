"""C20.1: resolve experimental length conflicts and demonstrate causal fidelity."""
import ast

def patch(source):
    source=source.replace('논점을 최대4문단에 통합한다.', '논점을 최대5문단에 통합한다.')
    source=source.replace('중복 표현을 줄여 특이사항은 약160자, 상세분석 각 문단은 약200자 이내를 지향한다. 필수 근거와 판단 조건이 있으면 분량보다 정확성을 우선한다.', '중복 표현만 줄이고 필수 근거와 판단 조건을 분량보다 우선한다.')
    marker="    payload = {'model':app.config()['model'], 'messages':messages,"
    assert source.count(marker)==1
    extra='''    if packet.get('preparation_mode')=='combined_with_generation':
        messages[0]['content']+='\\n아래는 가상의 작성 예시이며 현재 기업의 사실이나 수치가 아니다. 현재 자료에 복사하지 않는다.\\n예시1 원문: A사 세전이익 80, 법인세 120, 순이익 -40. 부적절: 금융비용 때문에 순손실이다. 적절한 본문: 세전 흑자 80에도 법인세 120이 반영되어 순손실 40을 기록했다. 적절한 특이사항: 세전 흑자이나 법인세 영향으로 순손실 전환. 손익 연결은 상세뿐 아니라 요약에도 보존한다.\\n예시2 원문: B사 자산 500→650, 차입 90→140, 자본 100→85, 조달용도 미명시. 부적절: 자산 취득을 위한 차입으로 부채비율 상승. 적절: 자산과 차입이 함께 증가했으며 조달용도는 확인되지 않는다. 차입 증가와 자본 감소는 재무부담을 높인다.\\n예시3 원문: C사 총자산 2021→2023 증가 60, 상세 건물은 2022→2023 증가 15. 적절: 총자산의 2년 증가와 건물의 1년 증가는 비교기간이 달라 같은 증감 구성으로 연결하지 않는다.\\n최종 작성 시 현재 기업의 earnings_bridge와 본문·특이사항이 일치하는지 확인한다. 특히 세전흑자·세후적자의 법인세 원인을 어느 쪽에서도 생략하지 않는다.'
'''
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
