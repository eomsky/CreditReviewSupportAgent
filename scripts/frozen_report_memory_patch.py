"""Reuse source-verified numeric records while planning a new report area."""
import ast

HELPER='''
def report_numeric_memory(prior,evidence):
    import copy,json
    from evidence_quality import VERSION
    available={s['id'] for s in evidence};records=[];seen=set()
    for view in prior.values():
        if view.get('refinement',{}).get('quality_version')!=VERSION:continue
        for row in view.get('evidence_assessment',{}).get('numeric_evidence',[]):
            ids=set(row.get('source_ids',[]))
            if not row.get('source_verified') or row.get('status')!='confirmed' or not ids or not ids<=available:continue
            identity=json.dumps(row,sort_keys=True,ensure_ascii=False)
            if identity in seen:continue
            seen.add(identity);records.append(copy.deepcopy(row))
    if not records:return None
    return {'facts':[],'tables':[],'source_excerpts':[],'conflicts':[],
            'numeric_evidence':records,'arithmetic_checks':[],'quality_version':VERSION}

'''

def patch(source):
    marker='def complete(run_dir, name, prompt, evidence, prior, report=False,'
    assert source.count(marker)==1
    source=source.replace(marker,HELPER+marker)
    marker='    packet=prepared_context.prepare(app,llm_stream,token_count,run_dir,name,evidence,manifest,outline if report else None,prompt,state,cancel_event,bases,fixed=fixed,report_context=report_context)'
    assert source.count(marker)==1
    replacement="    numeric_memory=report_numeric_memory(prior,evidence) if report else None\n"
    replacement+="    if numeric_memory:app.dump(run_dir/'report.reused-numeric-records.json',numeric_memory)\n"
    replacement+=marker[:-1]+",previous_packet=numeric_memory,fresh_ids={s['id'] for s in evidence} if numeric_memory else None)"
    source=source.replace(marker,replacement)
    ast.parse(source)
    return source
