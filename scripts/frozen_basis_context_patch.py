"""Expose exact-source provenance to semantic review; preserve basis distinctions."""
import ast

BASIS_RULES='''고정 재무표는 해당 표의 기간·단위·범위를 본문 비교의 기준으로 삼는다. 별도와 연결, 실적과 추정, 당기와 전기 수치를 서로 바꿔 비교하거나 기준 차이를 실적 악화·자료 오류로 해석하지 않는다. 기준이 확인되지 않으면 서로 직접 비교할 수 없음을 명시하고 같은 원문 범위 내 추세를 분석한다. 다른 기준의 수치가 유용하면 기준을 명시한 독립 문단으로 설명한다. 순손익의 원인을 설명할 때 영업손익→영업외손익→세전손익→법인세→순손익 연결을 원문에서 확인하고, 근거가 없는 인과를 단정하지 않는다. 내부 S1/P1/D1 같은 인덱스는 인용 필드에만 기록하며 본문에는 실제 문서명·기준으로 표현한다.'''


def patch(source):
    old="('caption','columns','rows')"
    assert source.count(old)==1
    source=source.replace(old,"('caption','columns','rows','source_binding')")
    marker='def eligible(draft):'
    source=source.replace(marker,'RULES+=' + repr('\n'+BASIS_RULES+' source_binding은 원문 표를 정확히 복사한 출처다. 동일 수치를 다른 문서의 기준으로 덮어쓰지 않는다. 수정이 필요하면 같은 정의·기간·단위의 더 적정한 원문 근거를 확인한다.')+'\n\n\n'+marker)
    ast.parse(source)
    return source
