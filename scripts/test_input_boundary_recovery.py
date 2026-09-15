"""Verify current recovery budget integration without model calls."""
import json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from frozen_input_boundary_patch import patch


class BoundaryRecoveryTest(unittest.TestCase):
    def test_output_partition_precedes_reduced_budget_generation(self):
        code=Path('outputs/frozen_candidates/C11-r1/code/scripts')
        sys.path.insert(0,str(code))
        ns={}
        exec(compile(patch((code/'llm_recovery.py').read_text(encoding='utf-8')),'candidate_recovery','exec'),ns)
        request={'max_tokens':16000,'messages':[{'role':'system','content':'instructions'},
                    {'role':'user','content':json.dumps({'draft':'indispensable body','sources':[]})}],
                 'structured_outputs':{'json':{'type':'object','properties':{'left':{'type':'string'},'right':{'type':'string'}},'required':['left','right']}}}
        calls=[]
        def complete(config,req,*args,**kwargs):
            calls.append(req)
            self.assertLessEqual(20500+req['max_tokens']+512,32768)
            fields=req['structured_outputs']['json']['properties']
            self.assertEqual(len(fields),1,'Must split before first generation')
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({k:'result' for k in fields})}}]}
        result=ns['complete'](SimpleNamespace(complete=complete),{},request,None,lambda messages:(20500,32768))
        self.assertEqual(len(calls),2)
        self.assertEqual(json.loads(result['choices'][0]['message']['content']),{'left':'result','right':'result'})
        self.assertEqual(request['max_tokens'],16000)
        self.assertEqual(calls[0]['max_tokens'],8000)


if __name__=='__main__':unittest.main()
