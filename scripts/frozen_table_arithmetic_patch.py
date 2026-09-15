import ast


def patch(source):
    marker='    # Review the final text, not duplicate historical before/after snapshots.'
    assert source.count(marker)==1
    source=source.replace(marker,"    from frozen_table_arithmetic import context as table_arithmetic\n    comparisons=list(table_arithmetic(draft))\n    if comparisons:result['source_table_arithmetic']=comparisons\n"+marker)
    marker='    system=with_reasoning(system)'
    assert source.count(marker)==1
    source=source.replace(marker,"    system+='\\nsource_table_arithmetic는 원문 완성표의 동일 행·명시된 두 기간을 직접 뺀 산술 결과다. 해당 표의 증감 비교를 검토할 때 시작기간/종료기간/단위를 함께 확인한다. 상세표의 증감 열을 다른 기간의 비교에 대입하지 않는다. 원문 표의 올바른 산술을 모델의 암산으로 오류라고 판정하지 않는다. 회계적 비교 가능성과 인과는 별도로 판단한다.'\n"+marker)
    ast.parse(source)
    return source
