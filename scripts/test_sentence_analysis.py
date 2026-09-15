import copy
import json
import unittest
from unittest.mock import patch
import business_report_test as review
import sentence_analysis


class SentenceAnalysisTests(unittest.TestCase):
    def test_sentence_context_evidence_and_tables_are_sent_without_mutation(self):
        state={'views':{'financial_accounts':{'title':'가. 재무제표 주요계정','tables':[{'rows':[['매출액',100,120]]}],'paragraphs':[{'id':'p','text':'기존 문단','sources':[{'id':'source','document_id':'doc','text':'원문 매출액 120','metadata':{}}]}]}}}
        before=copy.deepcopy(state)
        result={'summary':'판단 설명','evidence_assessment':'수치 근거','reasoning':'판단 연결','improvements':[], 'concept_title':'개념 구조','concept_steps':['매출','현금 회수'],'comparisons':[]}
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result)}}]}
        with patch.object(review.app,'config',return_value={'model':'test'}),patch.object(review.llm_stream,'complete',return_value=response) as call:
            actual=sentence_analysis.analyze(review.app,review.llm_stream,lambda m:(100,32000),state,{'paragraph_id':'p::part1','sentence':'선택 문장'})
        data=json.loads(call.call_args.args[1]['messages'][1]['content'])
        self.assertEqual(data['selected_sentence'],'선택 문장')
        self.assertEqual(data['sources'][0]['id'],'source')
        self.assertEqual(data['보고서 표'],state['views']['financial_accounts']['tables'])
        self.assertEqual(state,before);self.assertEqual(actual,result)

    def test_missing_evidence_is_not_fabricated(self):
        result={'summary':'확인 제한','evidence_assessment':'연결된 원문 없음','reasoning':'개념 설명','improvements':['원문 확인'], 'concept_title':'개념','concept_steps':[],'comparisons':[]}
        with patch.object(review.app,'config',return_value={'model':'test'}),patch.object(review.llm_stream,'complete',return_value={'choices':[{'message':{'content':json.dumps(result)}}]}) as call:
            sentence_analysis.analyze(review.app,review.llm_stream,lambda m:(100,32000),{}, {'sentence':'선택 문장','paragraph_id':'unknown'})
        self.assertEqual(json.loads(call.call_args.args[1]['messages'][1]['content'])['sources'],[])

    def test_empty_sentence_rejected_without_call(self):
        with self.assertRaises(ValueError):sentence_analysis.analyze(None,None,None,{}, {'sentence':''})


if __name__=='__main__':unittest.main()
