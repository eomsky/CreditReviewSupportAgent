import copy,json,threading,types,unittest
from pathlib import Path
from unittest.mock import patch
from frozen_review_reuse_patch import patch as transform


class ReviewReuseTests(unittest.TestCase):
    def test_finished_table_skipped_and_unsupported_edit_flagged(self):
        m=types.ModuleType('table_candidate')
        exec(transform(Path('outputs/frozen_candidates/C8/code/scripts/semantic_table_review.py').read_text(encoding='utf-8')),m.__dict__)
        base={'caption':'비율 (단위: %)','columns':['항목','2025'],'rows':[['유동비율',22]],'source_ids':['s'],'report_template':True,'quality_version':m.evidence_quality.VERSION}
        finished={**copy.deepcopy(base),'semantic_review_completed':True,'rows':[['유동비율',11]]}
        memory={'draft':{'tables':[finished,base],'paragraphs':[{'id':'p','text':'body','sources':[]}]},'evidence':[{'id':'s','document_id':'d','text':'2025 유동비율 22'}],'documents':[]}
        app=types.SimpleNamespace(lock=threading.RLock(),config=lambda:{'model':'test'},dump=lambda *a:None)
        response={'T0':{'columns':base['columns'],'rows':{'R0::유동비율':{'values':{'C1::2025':999},'source_ids':[],'reason':'unknown','calculation':''}},'omit_rows':[],'omit_columns':[],'layout_reason':'','caption':base['caption'],'unresolved':[],'unit_review':{'reason':'ratio','unit':'%'}}}
        def complete(llm,cfg,req,*args,**kw):
            self.assertEqual(list(req['structured_outputs']['json']['properties']),['T0'])
            return {'choices':[{'message':{'content':json.dumps(response,ensure_ascii=False)}}]}
        with patch.object(m.llm_recovery,'complete',side_effect=complete):
            result=m.review(app,None,None,Path('.'),'test',memory,{'run':{}},None)
        self.assertEqual(result['tables'][0]['rows'],[['유동비율',11]])
        self.assertEqual(result['tables'][1]['rows'],[['유동비율',22]])
        self.assertTrue(result['tables'][1]['verification_gaps'])
        self.assertFalse(result['tables'][1]['semantic_review_completed'])
        self.assertIn('원문 확인 필요',result['tables'][1]['caption'])
        self.assertEqual(memory['draft']['tables'][1]['rows'],[['유동비율',22]])


if __name__=='__main__':unittest.main()
