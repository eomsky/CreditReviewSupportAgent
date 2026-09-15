"""Avoid regenerating report cells that exactly project a reviewed source table."""
import ast


def patch(source):
    marker="    if state:\n        with app.lock:state['run']['stage']=stage+' · 생성 중'"
    assert source.count(marker)==1
    source=source.replace(marker,"    from frozen_report_table_reuse import bind as bind_report_tables\n    reused_report_tables=bind_report_tables(packet,prior,evidence) if report else {}\n"+marker)
    marker='        prepared_context.configure(schema,packet)'
    assert source.count(marker)==1
    source=source.replace(marker,marker+"\n        if reused_report_tables:\n            from frozen_report_table_reuse import configure as configure_reuse\n            configure_reuse(schema,reused_report_tables)\n            app.dump(run_dir/'report.source-table-reuse.json',reused_report_tables)\n            prompt+='\\n다음 표는 앞선 검토본의 원문 작성 표에서 동일 출처·항목·기간 좌표를 정확히 대조한 재사용 값이다. 해당 표의 rows는 재생성하지 않으며 프로그램이 원문 값과 단위를 복사한다. 본문 의미·기준 검토는 계속 수행한다. 다른 표와 다른 기준을 혼합하지 않는다. reused_source_tables='+app.json.dumps(reused_report_tables,ensure_ascii=False)")
    marker='    else:prepared_context.apply(result,packet,aliases)'
    assert source.count(marker)==1
    source=source.replace(marker,"    else:\n        from frozen_report_table_reuse import restore as restore_reuse, annotate as annotate_reuse\n        if reused_report_tables:restore_reuse(result,reused_report_tables,aliases)\n        prepared_context.apply(result,packet,aliases)\n        if reused_report_tables:annotate_reuse(result,packet,reused_report_tables)")
    ast.parse(source)
    return source
