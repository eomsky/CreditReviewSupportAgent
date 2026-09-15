import ast

RULE='numeric_evidence의 16개 한도를 표 앞 행부터 순서대로 전사하여 채우지 않는다. 표 원문은 다음 단계에도 전달된다. 이 배열에는 심사 결론·인과·산식을 검증하는 데 필요한 핵심 수치만 선택한다. 최신 실적의 핵심 수치와 실제 비교에 필요한 과거값을 우선하며, 동업계 평균과 추정치를 무조건 모두 전사하지 않는다. 손익 원인이나 적자 전환을 다루는 자료이면 같은 기간·기준의 영업이익, 금융비용, 세전손익, 법인세, 당기순손익을 먼저 확보하여 관계 인덱스를 연결한다. 원문에 해당 항목이 없으면 unknown 또는 conflicts로 남긴다. 원문 값 자체와 회계적 역할을 구분하고, 세전흑자에서 세후적자로 전환되면 법인세 영향을 빠뜨리지 않는다. 불필요한 숫자 반복을 줄이되 필요한 인과 검증은 생략하지 않는다.'


def patch(source):
    marker="    identity={'version':VERSION"
    assert source.count(marker)==1
    source=source.replace(marker,"    rules+='\\n'+"+repr(RULE)+"\n"+marker)
    ast.parse(source)
    return source
