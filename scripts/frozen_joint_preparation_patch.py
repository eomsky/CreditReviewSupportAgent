"""C13 experiment: combine preparation with generation for fully bound fixed tables."""
import ast

def patch(source):
    marker="    numeric_memory=report_numeric_memory(prior,evidence) if report else None"
    start=source.index(marker)
    end=source.index('    from frozen_report_table_reuse import bind as bind_report_tables',start)
    original=source[start:end]
    replacement='''    from frozen_exact_template_source import bind_templates as joint_bind
    from review_documents import PRIORITIES as joint_priorities
    joint_tables=joint_bind(evidence,bases,joint_priorities) if fixed and not report else {}
    joint_ready=bool(bases) and len(joint_tables)==len(bases)
    if joint_ready:
        packet={key:[] for key in ('facts','tables','numeric_evidence','calculations','arithmetic_checks','conflicts','source_excerpts','search_queries','planned_tables')}
        packet['preparation_mode']='combined_with_generation'
        packet['quality_status']='unassessed'
        prompt+='\\n이번에는 별도 사전 검토 응답을 생략하고 원문 검토와 초안 작성을 한 번에 수행한다. 원문과 기간·단위·항목이 정확히 대응한 고정표는 프로그램이 그대로 표시한다. 본문 작성 전에 sources에서 동일 기준의 손익과 자산·차입 변화를 대조한다. 세전이익·법인세·순이익의 연결과 지표 산식을 구분하여 설명한다. 빈 준비 기록은 자료가 없다는 뜻이 아니며 모든 사실은 sources에서 확인한다. 원문에서 확인하지 못한 인과관계는 단정하지 않는다.'
        app.dump(run_dir/(name+'.preparation.json'),packet)
        app.dump(run_dir/(name+'.joint-preparation.json'),{'mode':'combined_with_generation','source_table_count':len(joint_tables),'quality_pass':False,'separate_preparation_call':False})
    else:
'''+''.join('    '+line if line.strip() else line for line in original.splitlines(keepends=True))
    source=source[:start]+replacement+source[end:]
    ast.parse(source)
    return source
