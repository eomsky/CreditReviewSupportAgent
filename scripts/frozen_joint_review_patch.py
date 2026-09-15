"""Defer redundant preparation to the unchanged deep review over retained sources."""
def patch(source):
    start=source.index('def prepare_memory(')
    end=source.index('\n\ndef refine(',start)
    original=source[start:end]
    header=original.splitlines()[0]
    replacement=header+'''
    memory=copy.deepcopy(memory)
    memory['prepared_context']=memory.get('prepared_context') or memory['draft'].get('evidence_assessment',{})
    # No synthetic quality_version: the single review must assess original evidence.
    return memory
'''
    source=source[:start]+replacement+source[end:]
    anchor="    memory=prepare_memory(app,llm,token_count,folder,key,memory,prompt,state,cancel_event)"
    assert source.count(anchor)==1
    source=source.replace(anchor,"    prompt+='\\n이번 검토에서는 별도 준비 호출을 재수행하지 않았다. 기존 준비 요약은 검수 완료 보증이 아니며, 제공 원문과 고정표를 직접 대조하여 수치·기간·단위·인과를 심층 검토한다. 확인이 부족하면 남은 자료 요구를 명시한다. 자본변동 원인을 순손실로 단정하려면 동일 기준과 변동내역 근거가 필요하다. 표 간 기준 미확정은 동일 문서라는 이유만으로 해소되지 않는다.'\n"+anchor)
    return source
