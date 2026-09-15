import ast,copy,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import business_report_test as api
from frozen_parallel_patch import patch as transform

class PhaseTests(unittest.TestCase):
    def test_dependency_barriers_and_all_reviewed_inputs(self):
        source=Path('outputs/experiments/20260914/frozen/scripts/business_report_test.py').read_text(encoding='utf-8')
        tree=ast.parse(transform(source))
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker')
        namespace=dict(api.__dict__);namespace['_experiment_local']=threading.local()
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'candidate','exec'),namespace)
        state={'id':'isolated-test','revision':0,'views':{},'report':{},'run':{'status':'running'}}
        generated=set();reviewed=set();guard=threading.Lock();barrier=threading.Barrier(2)
        active=[0,0]
        def complete(folder,key,prompt,evidence,prior,**kwargs):
            with guard:
                active[0]+=1;active[1]=max(active)
            if key in api.app.VIEWS[:2]:barrier.wait(timeout=4)
            if key=='summary_2':self.assertEqual(set(prior),set(api.app.VIEWS[:5]))
            with guard:generated.add(key);active[0]-=1
            return {'title':key,'paragraphs':[{'text':'保持된 분석','sources':[]}],'tables':[]}
        def refine(*args):
            key,memory=args[4:6]
            self.assertEqual(generated,set(api.app.VIEWS))
            with guard:reviewed.add(key)
            r=copy.deepcopy(memory['draft']);r['refinement']={'done':True};return r
        def report(*args):
            self.assertEqual(reviewed,set(api.app.VIEWS))
            self.assertEqual(args[3]['run']['completed_calls'],12)
            self.assertTrue(all(x.get('refinement') for x in args[6].values()))
        payload={'target_views':api.app.VIEWS+['report'],'outline':['custom'],'generation_prompts':{k:[{'text':'instructions'}] for k in api.app.VIEWS+['report']}}
        with tempfile.TemporaryDirectory() as tmp,patch.object(api.app,'ROOT',Path(tmp)),patch.object(api.STORE,'manifest',return_value=[]),patch.object(api.review_refinement,'prepare_memory',side_effect=lambda *a:a[5]),patch.object(api.review_refinement,'refine',side_effect=refine),patch.object(api.semantic_table_review,'eligible',return_value=False),patch.object(api.report_pipeline,'run',side_effect=report):
            namespace.update(case_state=lambda p:state,persist_case=lambda s:None,select_sources=lambda *a:[],complete=complete)
            namespace['worker'](payload,'test')
        self.assertEqual(state['run']['status'],'completed',state['run'])
        self.assertEqual(active[1],2)

if __name__=='__main__':unittest.main()
