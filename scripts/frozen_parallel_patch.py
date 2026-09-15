"""Preserve frozen phase contents; overlap independent opinion jobs only."""
import ast

def patch(source):
    start=source.index('def worker(payload, run_id):')
    end=source.index('\napp.worker = worker',start)
    worker=source[start:end]
    old='        for i, key in enumerate(targets):\n            check_cancel()'
    new='        def draft_one(item):\n            i,key=item\n            _experiment_local.tag="draft:"+key\n            check_cancel()'
    assert worker.count(old)==1
    worker=worker.replace(old,new)
    marker='        # All requested drafts must exist before any second-pass call begins.'
    dispatch='''        independent=[(i,k) for i,k in enumerate(targets) if k not in ('summary_2','report')]
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(draft_one,independent))
        for item in [(i,k) for i,k in enumerate(targets) if k in ('summary_2','report')]:
            draft_one(item)
'''
    assert worker.count(marker)==1
    worker=worker.replace(marker,dispatch+marker)
    old='        for i, key in enumerate(review_targets):\n            check_cancel()'
    new='        def review_one(item):\n            i,key=item\n            _experiment_local.tag="review:"+key\n            check_cancel()'
    assert worker.count(old)==1
    worker=worker.replace(old,new)
    marker='        if report_requested:\n            report_pipeline.run'
    dispatch='''        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(review_one,list(enumerate(review_targets))))
        with app.lock:
            state['run']['completed_calls']=len(targets)+len(review_targets)
        _experiment_local.tag='report'
'''
    assert worker.count(marker)==1
    worker=worker.replace(marker,dispatch+marker)
    result=source[:start]+'_experiment_local=threading.local()\n\n'+worker+source[end:]
    ast.parse(result)
    return result
