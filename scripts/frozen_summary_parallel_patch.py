"""Start source-grounded summary drafting without an unused draft barrier."""
import ast

def patch(source):
    marker="raw = complete(folder, key, prompt, evidence, generated if key in ('summary_2','report') else {},"
    assert source.count(marker)==1
    source=source.replace(marker,"raw = complete(folder, key, prompt, evidence, generated if key=='report' else {},")
    before='''        independent=[(i,k) for i,k in enumerate(targets) if k not in ('summary_2','report')]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda item:attempt(draft_one,item,"draft"),independent))
        for item in [(i,k) for i,k in enumerate(targets) if k in ('summary_2','report')]:
            attempt(draft_one,item,"draft")'''
    after='''        independent=[(i,k) for i,k in enumerate(targets) if k!='report']
        independent.sort(key=lambda item:item[1]!='summary_2')
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda item:attempt(draft_one,item,"draft"),independent))
        for item in [(i,k) for i,k in enumerate(targets) if k=='report']:
            attempt(draft_one,item,"draft")'''
    assert source.count(before)==1
    source=source.replace(before,after)
    ast.parse(source)
    return source
