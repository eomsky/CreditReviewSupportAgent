import ast


def patch(source):
    marker='        bases=report_tables.CATALOG'
    assert source.count(marker)==1
    source=source.replace(marker,marker+"\n        from frozen_template_selection import select as select_template_examples\n        template_index=[[t['id'],t['title'],t.get('use','')] for t in bases]\n        bases,template_selection=select_template_examples(bases,outline,getattr(STORE,'vector',None))\n        app.dump(run_dir/'report.template-selection.json',template_selection)\n        prompt+='\\nbase_templates는 이번 목차와 관련된 상세 양식 예시다. 전체 양식의 [ID,제목,용도] 목록은 '+app.json.dumps(template_index,ensure_ascii=False,separators=(',',':'))+'. 상세 목록에 없어도 원문과 심사 질문에 적합한 표를 직접 설계할 수 있다.'")
    ast.parse(source)
    return source
