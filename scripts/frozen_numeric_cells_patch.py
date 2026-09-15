import ast

RULE='금액만 담은 미확정 고정표의 숫자 셀은 직접 숫자를 반환하지 않고 원문 참조 객체로 반환한다. 모든 숫자 셀을 검토한다. sources의 L번호는 원문 줄이다. 각 숫자는 [N0=값], [N1=값]처럼 표시된다. value_index는 선택한 N 뒤의 번호 그대로다. 숫자를 다시 세거나 1을 더하지 않는다. source_id/line/value_index로 정확한 값 위치를 선택하고 header_source_id는 같은 표의 기간·단위가 명시된 원문이다. period는 대상 열의 연도 4자리이며 원문의 당기/전기 머리글과 해당 숫자 열을 연결한다. source_unit은 원문에 적힌 단위이고 프로그램이 표의 표시 단위로 환산한다. 다른 기간에 값을 채우지 않는다. 원문에서 확인하지 못한 기간은 null이다. source_binding 표는 원문 그대로 복사한 표이므로 변경값을 만들어 내지 말고 기준 충돌은 unresolved에 설명한다.'


def patch(source):
    source='from frozen_numeric_cells import numbered, schema_cells, scoped_evidence, eligible as numeric_reference_eligible, restore as restore_numeric_cells\n'+source
    source=source.replace("and (not t.get('semantic_review_completed')", "and not t.get('source_binding') and (not t.get('semantic_review_completed')")
    source=source.replace("if not t.get('needs_evidence')]", "if not t.get('needs_evidence') and not t.get('source_binding')]")
    marker='    tables=[t for _,t in locations]'
    assert source.count(marker)==1
    source=source.replace(marker,marker+"\n    if not tables:return draft\n    evidence=scoped_evidence(tables,evidence)\n    aliases={f'S{i+1}':s for i,s in enumerate(evidence)}")
    marker='    app.dump(folder/(key+\'.table-review.request.json\'),request)'
    extra="""    request['structured_outputs']['json']=schema_cells(request['structured_outputs']['json'],tables,list(aliases))
    request['messages'][0]['content']+='\\n'+("""+repr(RULE)+""" if any(numeric_reference_eligible(t) for t in tables) else '이번 표의 값은 실제 JSON 숫자·문자열·null로 작성한다. S1,L2,N0 등 내부 원문 위치를 셀 값으로 반환하지 않는다. 원문 ID는 source_ids에만 기록한다.')
    source_body=json.loads(request['messages'][1]['content'])
    if any(numeric_reference_eligible(t) for t in tables):
        for item in source_body['sources']:item['text']=numbered(item['text'])
    request['messages'][1]['content']=json.dumps(source_body,ensure_ascii=False)
"""
    assert source.count(marker)==1
    source=source.replace(marker,extra+marker)
    marker="    result=plain_addresses(json.loads(response['choices'][0]['message']['content']));audit=[]"
    assert source.count(marker)==1
    source=source.replace(marker,marker+"\n    numeric_audit=restore_numeric_cells(result,tables,aliases)\n    app.dump(folder/(key+'.numeric-cell-audit.json'),numeric_audit)")
    ast.parse(source)
    return source
