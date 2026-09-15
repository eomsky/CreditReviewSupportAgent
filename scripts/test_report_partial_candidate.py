import copy,json,types,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
import business_report_test as api
from frozen_report_partial_patch import patch as transform


class PartialReportTests(unittest.TestCase):
    def test_failed_middle_group_keeps_other_groups_and_runs_integration(self):
        module=types.ModuleType('partial_candidate')
        exec(transform(Path('outputs/frozen_candidates/C7/code/scripts/report_pipeline.py').read_text(encoding='utf-8')),module.__dict__)
        source={'id':'source','document_id':'doc','text':'source','metadata':{'required':True}}
        opinions={key:{'paragraphs':[{'id':key,'text':'reviewed','sources':[source]}],'refinement':{'done':True}} for key in api.app.VIEWS}
        state={'id':'test','revision':0,'run':{'completed_calls':12,'total_calls':19,'target_views':['report']}}
        outline=[{'title':str(i),'description':''} for i in range(3)]
        reviewed=[]
        def complete(folder,key,prompt,evidence,prior,**kw):
            if kw['outline'][0]['title']=='1':raise ValueError('injected failure')
            api.app.dump(folder/'report.evidence.json',[source])
            return {'sections':[{'title':x['title'],'paragraphs':[{'id':x['title'],'text':'verified body','sources':[source]}]} for x in kw['outline']]}
        def refine(app,llm,count,folder,key,memory,*args):
            reviewed.append(key);return copy.deepcopy(memory['draft'])
        with tempfile.TemporaryDirectory() as directory,patch.object(api,'complete',side_effect=complete),patch.object(api.STORE,'select',return_value=[source]),patch.object(api.review_refinement,'refine',side_effect=refine),patch.object(api,'persist_case'),patch.object(module,'pdf_check',return_value={'target_met':True}):
            with self.assertRaisesRegex(ValueError,'일부 영역 실패'):
                module.run(api,{'generation_prompts':{'report':[]}},Path(directory),state,[{'id':'doc','name':'doc','required':True}],outline,opinions,lambda:None,None)
            self.assertEqual([s['title'] for s in state['report']['sections']],['0','2'])
            self.assertIn('report',reviewed)
            self.assertEqual(set(reviewed),{'report-area-1','report-area-3','report'})
            self.assertEqual(json.loads((Path(directory)/'report.area-failures.json').read_text())[0]['area'],1)


if __name__=='__main__':unittest.main()
