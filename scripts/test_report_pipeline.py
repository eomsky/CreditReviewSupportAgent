import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import business_report_test as api
import report_pipeline as pipeline


class ReportPipelineTests(unittest.TestCase):
    def test_report_plan_reviews_existing_drafts_without_regenerating(self):
        existing={k:{'paragraphs':[{'text':'existing'}]} for k in api.app.VIEWS}
        existing['summary_2']['refinement']={'done':True,'quality_version':api.review_refinement.evidence_quality.VERSION}
        before=copy.deepcopy(existing)
        drafts,reviews,report=api.generation_plan({'target_views':['report']},existing)
        self.assertEqual(drafts,[])
        self.assertEqual(reviews,api.app.VIEWS[:5])
        self.assertTrue(report)
        self.assertEqual(existing,before)

    def test_report_plan_generates_only_missing_dependencies(self):
        existing={k:{'paragraphs':[{'text':'existing'}],'refinement':{'done':True,'quality_version':api.review_refinement.evidence_quality.VERSION}} for k in api.app.VIEWS}
        del existing[api.app.VIEWS[1]]
        self.assertEqual(api.generation_plan({'target_views':['report']},existing),
                         ([api.app.VIEWS[1]],[api.app.VIEWS[1]],True))
        self.assertEqual(api.generation_plan({'target_views':['summary_2']},existing),
                         (['summary_2'],['summary_2'],False))

    def test_worker_resumes_review_before_report(self):
        state={'id':'resume-fixture','revision':1,'run':{},'views':{k:{'paragraphs':[{'text':'existing','sources':[]}]} for k in api.app.VIEWS}}
        state['views']['summary_2']['refinement']={'done':True,'quality_version':api.review_refinement.evidence_quality.VERSION}
        payload={'target_views':['report'],'outline':['custom'],'generation_prompts':{k:[{'text':'instructions'}] for k in api.app.VIEWS+['report']}}
        reviewed=[]
        def refine(*args):
            key,memory=args[4:6]
            reviewed.append(key)
            result=copy.deepcopy(memory['draft']);result['refinement']={'done':True,'quality_version':api.review_refinement.evidence_quality.VERSION}
            return result
        def report(*args):
            self.assertTrue(all(v.get('refinement') for v in args[6].values()))
            self.assertEqual(state['run']['completed_calls'],5)
        with tempfile.TemporaryDirectory() as root,patch.object(api.app,'ROOT',Path(root)),patch.object(api,'case_state',return_value=state),patch.object(api,'persist_case'),patch.object(api.review_refinement,'prepare_memory',side_effect=lambda *args:args[5]),patch.object(api.STORE,'manifest',return_value=[]),patch.object(api,'select_sources',return_value=[]),patch.object(api,'complete') as generate,patch.object(api.review_refinement,'refine',side_effect=refine),patch.object(pipeline,'run',side_effect=report):
            api.worker(payload,'resume-run')
        generate.assert_not_called()
        self.assertEqual(reviewed,api.app.VIEWS[:5])
        self.assertEqual(state['run']['status'],'completed')

    def test_wire_ids_round_trip_without_changing_text(self):
        data={'paragraphs':[{'id':'paragraph-long','text':'S1은 본문 그대로','sources':[{'id':'source-long','text':'원문'}]}],'tables':[{'source_ids':['source-long']}],'additions':[{'after_id':'paragraph-long','source_ids':['source-long'],'text':'추가'}]}
        mapping={'paragraph-long':'P1','source-long':'S1'}
        wire=api.review_refinement.remap_ids(data,mapping)
        self.assertEqual(wire['paragraphs'][0]['sources'][0]['id'],'S1')
        self.assertEqual(wire['paragraphs'][0]['text'],'S1은 본문 그대로')
        self.assertEqual(api.review_refinement.remap_ids(wire,{v:k for k,v in mapping.items()}),data)

    def test_final_review_input_excludes_historical_copies(self):
        draft={'paragraphs':[{'text':'최종 본문','sources':[{'id':'s'}]}],'tables':[{'rows':[[0,None]]}],'refinement':{'changes':['이전 본문']}}
        compact=api.review_refinement.draft_input(draft)
        self.assertEqual(compact['paragraphs'][0]['text'],'최종 본문')
        self.assertEqual(compact['tables'],draft['tables'])
        self.assertNotIn('refinement',compact)
        self.assertIn('refinement',draft)

    def test_area_evidence_keeps_citations_fresh_sources_and_required_documents(self):
        sources=[{'id':'body','document_id':'d1'},{'id':'table','document_id':'d1'},{'id':'other-area','document_id':'d1'},{'id':'required','document_id':'d2'}]
        area={'sections':[{'paragraphs':[{'sources':[sources[0]]}],'tables':[{'source_ids':['table']}]}]}
        fresh=[{'id':'new','document_id':'d1'}]
        chosen=pipeline.area_sources(area,sources,fresh,[{'id':'d1','required':True},{'id':'d2','required':True}])
        self.assertEqual({s['id'] for s in chosen},{'body','table','new','required'})
        self.assertEqual(len(sources),4)

    def test_custom_outline_order_preserved(self):
        for n in range(1,12):
            rows=[{'title':str(i),'description':'custom'} for i in range(n)]
            parts=pipeline.groups(rows)
            self.assertEqual([x for part in parts for x in part],rows)
            self.assertLessEqual(len(parts),3)
            self.assertTrue(all(parts))

    def test_unreviewed_opinions_rejected(self):
        with self.assertRaises(api.DocumentError):
            pipeline.run(api,{'generation_prompts':{'report':[]}},Path('.'),{'run':{'completed_calls':0}},[],[],{},lambda:None,None)

    def test_split_final_inputs_unique_ids_and_bounded_supplement(self):
        source={'id':'s','document_id':'doc','text':'확인 근거','selection_relevance':1,'metadata':{'required':True}}
        final={k:{'paragraphs':[{'id':k,'text':'검토 완료 내용','sources':[source]}],'tables':[{'columns':['확인값'],'rows':[[10]]}],'refinement':{'done':True,'quality_version':api.review_refinement.evidence_quality.VERSION}} for k in api.app.VIEWS}
        state={'id':'fixture','run':{'completed_calls':12,'total_calls':19,'target_views':['report']*19},'revision':0}
        outline=[{'title':str(i),'description':'custom'} for i in range(7)]
        calls=[]
        def complete(folder,key,prompt,evidence,prior,**kwargs):
            self.assertTrue(prior)
            for key,value in prior.items():self.assertEqual(value,final[key]);self.assertIn('tables',value)
            api.app.dump(folder/'report.evidence.json',[source])
            calls.append(('draft',kwargs['outline']))
            return {'sections':[{'title':x['title'],'paragraphs':[{'id':folder.name+'-'+x['title'],'text':'근거 있는 본문','sources':[source]}]} for x in kwargs['outline']]}
        def refine(app,llm,count,folder,key,memory,prompt,state,cancel):
            calls.append(('review',key));return copy.deepcopy(memory['draft'])
        checks=[{'target_met':False},{'target_met':False},{'target_met':True}]
        with tempfile.TemporaryDirectory() as root,patch.object(api.STORE,'select',return_value=[source]),patch.object(api,'complete',side_effect=complete),patch.object(api,'persist_case'),patch.object(api.review_refinement,'refine',side_effect=refine),patch.object(pipeline,'pdf_check',side_effect=checks):
            pipeline.run(api,{'generation_prompts':{'report':[]}},Path(root),state,[],outline,final,lambda:None,threading.Event())
        self.assertEqual(len(calls),8)
        self.assertEqual(state['run']['completed_calls'],20)
        self.assertEqual(state['run']['total_calls'],20)
        report=state['report'];self.assertEqual([s['title'] for s in report['sections']],[str(i) for i in range(7)])
        ids=[p['id'] for s in report['sections'] for p in s['paragraphs']]
        self.assertEqual(len(ids),len(set(ids)))


if __name__=='__main__':unittest.main()

