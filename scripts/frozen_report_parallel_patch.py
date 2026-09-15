"""Overlap independent detailed report reviews; retain final integration review."""
import ast

def patch(source):
    start=source.index('    for i,part in enumerate(groups(outline)):',source.index('    # Stage 1:'))
    end=source.index("    memory={'draft':assembled",start)
    body=source[start:end]
    split=body.index("        assessments[i]=")
    work=body[:split]
    apply=body[split:]
    work=work.replace('    for i,part in enumerate(groups(outline)):',
        '    def review_area(item):\n        i,part=item\n        if hasattr(api,"_experiment_local"):api._experiment_local.tag="report-review:"+str(i+1)')
    work=work.replace("        collected.update({s['id']:s for s in fresh})\n        evidence=list(collected.values())",
        "        area_collected=dict(collected)\n        area_collected.update({s['id']:s for s in fresh})\n        evidence=list(area_collected.values())")
    work+='        return i,reviewed,fresh\n'
    dispatch='''    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        reviewed_areas=list(pool.map(review_area,list(enumerate(groups(outline)))))
    for i,reviewed,fresh in reviewed_areas:
        collected.update({s['id']:s for s in fresh})
'''
    tail="    evidence=list(collected.values())\n    if hasattr(api,'_experiment_local'):api._experiment_local.tag='report-integration'\n"
    result=source[:start]+work+dispatch+apply+tail+source[end:]
    ast.parse(result)
    return result
