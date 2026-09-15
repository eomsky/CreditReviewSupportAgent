"""Experimental report-area overlap; full outline and final integration preserved."""
import ast

def patch(source):
    start=source.index('    for i,part in enumerate(groups(outline)):')
    end=source.index('    evidence=list(collected.values())',start)
    old=source[start:end]
    block=old.replace('    for i,part in enumerate(groups(outline)):', '    def draft_area(item):\n        i,part=item\n        if hasattr(api,"_experiment_local"):api._experiment_local.tag="report-draft:"+str(i+1)')
    block=block.replace("        assessments.append(raw.get('evidence_assessment',{}))", "        assessment=raw.get('evidence_assessment',{})")
    block=block.replace("        preparation=sub/'report.preparation.json'", "        excerpts=[]\n        preparation=sub/'report.preparation.json'")
    block=block.replace('            prepared_excerpts.extend(', '            excerpts.extend(')
    block=block.replace("        collected.update({s['id']:s for s in included})", '')
    block=block.replace("        assembled['sections'].extend(raw['sections'])\n        with app.lock:\n            state['report']=copy.deepcopy(assembled);state['revision']+=1;run.update(completed_calls=start+i+1,preview='');api.persist_case(state)", "        return i,raw,assessment,excerpts,included")
    # Parallel areas cannot see one another's unfinished tables. Tell the planner
    # the ownership boundary explicitly; integration still checks all areas.
    block=block.replace("        raw=api.complete(", "        planning_context['parallel_sections']=[[x['title'] for x in group] for group in groups(outline)]\n        instructions+='\\n다른 영역이 동시에 작성된다. 전체 목차와 이번 목차의 심사 질문을 구별하여 이번 영역에 직접 필요한 표만 선택한다. 다른 영역의 손익·재무·상환 표를 미리 중복 작성하지 않는다.'\n        raw=api.complete(")
    block+='''    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        drafted=list(pool.map(draft_area,list(enumerate(groups(outline)))))
    for i,raw,assessment,excerpts,included in drafted:
        assessments.append(assessment);prepared_excerpts.extend(excerpts)
        collected.update({s['id']:s for s in included})
        assembled['sections'].extend(raw['sections'])
        with app.lock:
            state['report']=copy.deepcopy(assembled);state['revision']+=1;run.update(completed_calls=start+i+1,preview='');api.persist_case(state)
'''
    assert 'assessments.append' not in block[:block.index('    import concurrent.futures')]
    result=source[:start]+block+source[end:]
    ast.parse(result)
    return result
