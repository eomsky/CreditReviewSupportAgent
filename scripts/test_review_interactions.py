import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import business_report_test as review
import review_chat

class InteractionTests(unittest.TestCase):
    def test_chat_excludes_generation_instructions(self):
        result=review_chat.messages({'request':'질문','system_prompt':'SHOULD_NOT_APPEAR','common_prompt':'SHOULD_NOT_APPEAR','prompts':[{'text':'SHOULD_NOT_APPEAR'}],'paragraphs':[{'id':'p1','text':'선택 문장'}],'history':[{'role':'user','text':'이전 질문'},{'role':'system','text':'SHOULD_NOT_APPEAR'}]},[])
        self.assertNotIn('SHOULD_NOT_APPEAR',json.dumps(result))
        self.assertIn('선택 문장',result[-1]['content'])
        self.assertEqual(result[1]['content'],'이전 질문')

    def test_settings_hide_and_preserve_key(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'chat.json'
            path.write_text(json.dumps({'base_url':'http://localhost/v1','model':'chat','api_key':'private-test'}))
            with patch.object(review_chat,'CONFIG',path):
                result=review_chat.settings({'action':'save','base_url':'http://localhost/v1','model':'other','api_key':''})
                self.assertNotIn('api_key',result)
                self.assertEqual(review_chat.config()['api_key'],'private-test')

    def complete(self,status,source_ids,reason='이 항목과 관련 없음'):
        doc={'id':'doc1','name':'필수.pdf','required':True,'description':'','priority':'보통'}
        evidence=[{'id':'original-id','document_id':'doc1','text':'자료','metadata':doc,'selection_relevance':1}]
        response={'title':'항목','paragraphs':[{'heading':'','text':'의견','source_ids':source_ids}],'required_document_reviews':[{'document_id':'doc1','status':status,'reason':reason}]}
        response['paragraphs'][0]['sources']=evidence if source_ids else []
        review.reconcile_required_reviews(response,[response],[doc])
        return response

    def test_required_not_used_reason_preserved(self):
        result=self.complete('not_used',[])
        self.assertEqual(result['required_document_reviews'][0]['reason'],'이 항목과 관련 없음')

    def test_false_reflected_rejected(self):
        self.assertEqual(self.complete('reflected',[])['required_document_reviews'][0]['status'],'not_used')

    def test_cited_document_cannot_be_not_used(self):
        self.assertEqual(self.complete('not_used',['S1'])['required_document_reviews'][0]['status'],'reflected')

if __name__=='__main__':unittest.main()
