"""Bound internal audit verbosity; keep original report text limits and all checks."""
def patch(source):
    anchor="    schema['properties']={'quality_checks':checks,**schema['properties']}"
    assert source.count(anchor)==1
    source=source.replace(anchor,"    for category in checks['properties'].values():category['properties']['reason']['maxLength']=140\n"+anchor)
    anchor="            'draft':draft_input(request_draft),'documents':remap_ids(memory['documents'],ids),"
    assert source.count(anchor)==1
    focus=('모든 문단을 검토하되 내부 품질 reason은 짧은 완결문으로 쓴다. 본문을 축약하지 않는다. '
           '표의 작성 기준이 불명확하면 요약표 총액과 상세표 건물을 특히/구성/기여로 연결하지 않는다. '
           '자본변동표 등 직접 근거가 없으면 자본 감소 원인을 순손실 반영으로 단정하지 않고 원인 확인 필요를 쓴다. '
           '차입 만기 연장은 원금 상환시점 조정이다. 이자율·현금창출 개선 근거 없이 이를 이자상환능력 개선으로 쓰지 않는다. '
           '예: 만기 연장 시 단기 원금 부담 완화 가능, 이자 부담 개선은 별도 확인 필요. '
           '추가 검토 쟁점에서 발견한 오류는 실제 revisions에 반영하고, 이미 충분한 설명은 재작성하지 않는다.')
    return source.replace(anchor,anchor+"\n            'mandatory_review_focus':"+repr(focus)+",")
