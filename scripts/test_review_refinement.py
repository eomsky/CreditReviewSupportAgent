import copy
import json
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
import review_refinement as refinement
import business_report_test as review


class RefinementTests(unittest.TestCase):
    def test_all_views_short_ids_restore_original_citations(self):
        def complete(config, request, progress, **kwargs):
            user=json.loads(request['messages'][1]['content'])
            self.assertEqual(user['draft']['paragraphs'][0]['id'],'P1')
            self.assertEqual(user['compressed_sources'][0]['id'],'S1')
            response=refinement.remap_ids(self.response,{'p1':'P1','p2':'P2','src1':'S1'})
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(response)}}]}
        memory={'prepared_context':{'quality_version':refinement.evidence_quality.VERSION},'draft':self.draft,'evidence':self.evidence,'compressed_sources':self.evidence,'documents':[]}
        for key in ['summary_2','financial_accounts','cashflow_repayment','customer_concentration','report-part-1']:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                result=refinement.refine(review.app,SimpleNamespace(complete=complete),lambda messages:(100,32768),Path(folder),key,memory,'검토',{'run':{}},None)
                self.assertEqual(result['paragraphs'][0]['id'],'p1')
                self.assertEqual(result['paragraphs'][0]['sources'][0]['id'],'src1')

    def setUp(self):
        self.evidence=[{'id':'src1','document_id':'doc1','text':'매출액 120. 전년 매출액 100.','metadata':{'required':True}}]
        self.draft={'title':'의견','tables':[{'rows':[['매출액',100,120]]}], 'paragraphs':[
            {'id':'p1','heading':'분석의견','text':'매출액이 증가하였다.','sources':self.evidence},
            {'id':'p2','heading':'','text':'추가 확인이 필요하다.','sources':[]}]}
        self.response={'revisions':[
            {'paragraph_id':'p1','action':'revise','text':'매출액은 100에서 120으로 증가하였다.','source_ids':['src1'],'reason':'비교 수치 보완'},
            {'paragraph_id':'p2','action':'keep','text':'','source_ids':[],'reason':''}],
            'additions':[{'after_id':'p1','text':'증가율은 20%이다.','source_ids':['src1'],'reason':'변화 설명'}],
            'remaining_gaps':['증가 원인 확인 필요'],
            'information_guidance':{'explanation':'매출 증가의 구체적인 원인이 확인되지 않았습니다.','needed_contents':['매출 증가 원인']}}

    def test_patch_preserves_tables_ids_and_untouched_text(self):
        result=refinement.apply_changes(self.draft,self.response,self.evidence)
        self.assertEqual(result['tables'],self.draft['tables'])
        self.assertEqual([p['id'] for p in result['paragraphs']],['p1','p1-addition-0','p2'])
        self.assertEqual(result['paragraphs'][-1],self.draft['paragraphs'][-1])
        self.assertEqual(self.draft['paragraphs'][0]['text'],'매출액이 증가하였다.')
        self.assertEqual(result['refinement']['information_guidance'],self.response['information_guidance'])

    def test_omission_duplicate_unknown_citation_and_large_deletion_rejected(self):
        for mode in ['omit','duplicate','citation','delete']:
            response=copy.deepcopy(self.response)
            if mode=='omit':response['revisions'].pop()
            if mode=='duplicate':response['revisions'][1]=response['revisions'][0]
            if mode=='citation':response['revisions'][0]['source_ids']=['fake']
            if mode=='delete':response['revisions'][0]['text']='삭제'
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                refinement.apply_changes(self.draft,response,self.evidence)

    def test_stream_incomplete_and_complete_revision_and_addition(self):
        text=json.dumps(self.response,ensure_ascii=False)
        changes=refinement.stream_changes(text)
        self.assertEqual([r['kind'] for r in changes],['revise','add'])
        self.assertTrue(changes[0]['complete'])
        partial='{"revisions":[{"paragraph_id":"p1","action":"revise","text":"매출액은 120'
        self.assertEqual(refinement.stream_changes(partial)[0],{'kind':'revise','id':'p1','text':'매출액은 120','complete':False})

    def test_compression_preserves_source_identity_and_input_tables(self):
        evidence=copy.deepcopy(self.evidence);evidence[0]['text']='매출액 120. '*300
        result=refinement.compact_sources(evidence,self.draft,300)[0]
        self.assertEqual(result['id'],'src1');self.assertTrue(result['text'])
        self.assertLess(len(result['text']),len(evidence[0]['text']))
        compact=refinement.draft_input(self.draft)
        self.assertEqual(compact['tables'],self.draft['tables'])
        self.assertNotIn('sources',compact['paragraphs'][0])

    def test_worker_finishes_six_reviews_before_report(self):
        state={'id':'test','views':{},'revision':0,'run':{'id':'run','status':'running'}}
        calls=[];targets=review.app.VIEWS
        def complete(folder,key,*args,**kwargs):
            calls.append(('draft',key));return copy.deepcopy(self.draft)
        def refine(app,llm,count,folder,key,memory,*args):
            self.assertEqual(len([c for c in calls if c[0]=='draft']),6)
            self.assertTrue((folder/(key+'.memory.json')).exists())
            calls.append(('refine',key));r=copy.deepcopy(memory['draft']);r['refinement']={};return r
        def report(api,payload,folder,state,manifest,outline,generated,*args):
            self.assertEqual(calls,[('draft',k) for k in targets]+[('refine',k) for k in targets])
            self.assertTrue(all('refinement' in generated[k] for k in targets))
            calls.append(('report','split'));state['run']['completed_calls']=19
        with tempfile.TemporaryDirectory() as root,patch.object(review.app,'ROOT',Path(root)),patch.object(review,'case_state',return_value=state),patch.object(review,'persist_case'),patch.object(refinement,'prepare_memory',side_effect=lambda *args:args[5]),patch.object(review.STORE,'manifest',return_value=[]),patch.object(review,'select_sources',return_value=self.evidence),patch.object(review,'complete',side_effect=complete),patch.object(review.review_refinement,'refine',side_effect=refine),patch.object(review.report_pipeline,'run',side_effect=report):
            review.worker({'outline':[str(i) for i in range(7)],'generation_prompts':{k:[{'text':''}] for k in targets+['report']}},'run')
        self.assertEqual(state['run']['total_calls'],19)
        self.assertEqual(state['run']['completed_calls'],19)
        self.assertEqual(state['run']['status'],'completed')

    def test_review_failure_preserves_all_completed_drafts(self):
        state={'id':'test','views':{},'revision':0,'run':{'id':'run','status':'running'}}
        with tempfile.TemporaryDirectory() as root,patch.object(review.app,'ROOT',Path(root)),patch.object(review,'case_state',return_value=state),patch.object(review,'persist_case'),patch.object(refinement,'prepare_memory',side_effect=lambda *args:args[5]),patch.object(review.STORE,'manifest',return_value=[]),patch.object(review,'select_sources',return_value=self.evidence),patch.object(review,'complete',return_value=copy.deepcopy(self.draft)),patch.object(review.review_refinement,'refine',side_effect=ValueError('failed')):
            review.worker({'target_views':['profitability'],'outline':['의견'],'generation_prompts':{'profitability':[{'text':''}]}},'run')
        self.assertEqual(state['views']['profitability'],self.draft)
        self.assertEqual(state['run']['status'],'failed')


if __name__=='__main__':unittest.main()
