import ast,copy,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import business_report_test as api
from frozen_parallel_patch import patch as parallel
from frozen_continue_patch import patch as continuation


class ContinuationTests(unittest.TestCase):
    def test_review_failure_still_attempts_report_and_remains_failed(self):
        text=Path('outputs/experiments/20260914/frozen/scripts/business_report_test.py').read_text(encoding='utf-8')
        tree=ast.parse(continuation(parallel(text)))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker')
        namespace=dict(api.__dict__);namespace['_experiment_local']=threading.local()
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'<worker>','exec'),namespace)
        state={'id':'test','revision':0,'views':{},'report':{},'run':{'status':'running'}}
        reviewed=[];reported=[]
        def generate(*args,**kwargs):return {'title':args[1],'paragraphs':[{'text':'원문 기반 초안','sources':[]}],'tables':[]}
        def refine(*args):
            key=args[4];reviewed.append(key)
            if key=='cashflow_repayment':raise ValueError('검토 입력 용량 오류')
            result=copy.deepcopy(args[5]['draft']);result['refinement']={'done':True};return result
        payload={'target_views':api.app.VIEWS+['report'],'outline':['custom'],'generation_prompts':{k:[{'text':'instructions'}] for k in api.app.VIEWS+['report']}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(api.app,'ROOT',Path(tmp)),patch.object(api.STORE,'manifest',return_value=[]),patch.object(api.review_refinement,'prepare_memory',side_effect=lambda *a:a[5]),patch.object(api.review_refinement,'refine',side_effect=refine),patch.object(api.semantic_table_review,'eligible',return_value=False),patch.object(api.report_pipeline,'run',side_effect=lambda *a:reported.append(True)):
            namespace.update(case_state=lambda p:state,persist_case=lambda s:None,select_sources=lambda *a:[],complete=generate)
            namespace['worker'](payload,'test')
        self.assertEqual(set(reviewed),set(api.app.VIEWS))
        self.assertEqual(reported,[True])
        self.assertEqual(state['run']['status'],'failed')
        self.assertEqual(state['run']['failed_steps'][0]['key'],'cashflow_repayment')
        self.assertLess(state['run']['completed_calls'],state['run']['total_calls'])


if __name__=='__main__':unittest.main()
