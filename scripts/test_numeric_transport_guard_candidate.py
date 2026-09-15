import copy,json,threading,types,unittest
from pathlib import Path
from unittest.mock import patch
from frozen_numeric_transport_guard_patch import patch as transform

class TransportGuardTests(unittest.TestCase):
    def test_position_code_not_displayed_or_marked_verified(self):
        module=types.ModuleType('guard_candidate')
        exec(transform(Path('outputs/frozen_candidates/C10/code/scripts/semantic_table_review.py').read_text(encoding='utf-8')),module.__dict__)
        table={'caption':'비율 (단위: %)','columns':['항목','2025'],'rows':[['비율',22]],'source_ids':['s'],'report_template':True}
        memory={'draft':{'tables':[copy.deepcopy(table)],'paragraphs':[{'id':'p','text':'본문','sources':[]}]},'evidence':[{'id':'s','document_id':'d','text':'2025 비율 22'}],'documents':[]}
        app=types.SimpleNamespace(lock=threading.RLock(),config=lambda:{'model':'test'},dump=lambda *args:None)
        response={'T0':{'columns':table['columns'],'rows':{'R0::비율':{'values':{'C1::2025':'S1,L0,N0'},'source_ids':['S1'],'reason':'original','calculation':''}},'omit_rows':[],'omit_columns':[],'layout_reason':'','caption':table['caption'],'unresolved':[],'unit_review':{'reason':'ratio','unit':'%'}}}
        def complete(llm,cfg,request,*args,**kwargs):
            spec=request['structured_outputs']['json']['properties']['T0']['properties']['rows']['properties']['R0::비율']['properties']['values']['properties']['C1::2025']
            self.assertEqual(spec['type'],['number','null'])
            return {'choices':[{'message':{'content':json.dumps(response)}}]}
        with patch.object(module.llm_recovery,'complete',side_effect=complete):
            result=module.review(app,None,None,Path('.'),'test',memory,{'run':{}},None)
        self.assertEqual(result['tables'][0]['rows'],table['rows'])
        self.assertFalse(result['tables'][0]['semantic_review_completed'])
        self.assertTrue(result['tables'][0]['verification_gaps'])
        self.assertEqual(memory['draft']['tables'][0],table)

if __name__=='__main__':unittest.main()
