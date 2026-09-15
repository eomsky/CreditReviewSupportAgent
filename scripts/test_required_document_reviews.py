import unittest
from business_report_test import reconcile_required_reviews,DocumentError

class RequiredReviewTests(unittest.TestCase):
    def test_self_report_cannot_create_a_citation(self):
        result={'required_document_reviews':[{'document_id':'d','status':'reflected','reason':'사용'}]}
        reconcile_required_reviews(result,[{'paragraphs':[{'sources':[]}]}],[{'id':'d','name':'원문'}])
        self.assertEqual(result['required_document_reviews'][0]['status'],'not_used')
        self.assertIn('인용이 없어',result['required_document_reviews'][0]['reason'])
    def test_actual_citation_controls_status(self):
        result={'required_document_reviews':[{'document_id':'d','status':'not_used','reason':'미사용'}]}
        reconcile_required_reviews(result,[{'paragraphs':[{'sources':[{'document_id':'d'}]}]}],[{'id':'d','name':'원문'}])
        self.assertEqual(result['required_document_reviews'][0]['status'],'reflected')
    def test_missing_document_review_still_fails(self):
        with self.assertRaises(DocumentError):reconcile_required_reviews({'required_document_reviews':[]},[],[{'id':'d','name':'원문'}])
