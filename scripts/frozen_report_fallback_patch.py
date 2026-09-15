"""Attempt the report from sources despite a missing independent opinion."""
import ast


def patch(source):
    old="""    if not generated or any(not generated.get(k,{}).get('refinement') for k in app.VIEWS):
        raise api.DocumentError('심사보고서는 종합의견1·2의 검토 완료본이 필요합니다. 먼저 전체 의견 생성을 실행해 주세요.')"""
    new="""    incomplete=[k for k in app.VIEWS if not generated.get(k,{}).get('refinement')]
    if incomplete:
        prompt+='\\n일부 선행 의견이 생성 또는 검토에 실패했다: '+', '.join(incomplete)+'. 해당 의견의 내용을 검증 완료 사실로 취급하지 않는다. 업로드 원문을 직접 확인하여 이번 보고서를 작성·검토하고, 원문으로 확인하지 못한 판단은 자료 부족으로 표시한다.'
        app.dump(folder/'report.upstream-failures.json',incomplete)"""
    assert source.count(old)==1
    source=source.replace(old,new)
    source=source.replace('prior_model_drafts는 검토가 끝난 의견이며 원문과 대조해 사용한다.','prior_model_drafts는 참고 의견이며 refinement가 있는 항목만 검토 완료본이다. 모두 원문과 대조해 사용한다.')
    ast.parse(source)
    return source
