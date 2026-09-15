"""Integration checks for isolated F7 adapters; no server or live case writes."""
import copy
import json
import sys
import threading
import types
import unittest
from pathlib import Path
from unittest.mock import patch as mocked

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'outputs/frozen_candidates/F6/code/scripts'))
from frozen_review_order_patch import patch as order_patch
from frozen_keep_encoding_patch import patch as keep_patch
from frozen_assessment_reference_patch import HELPERS


class Adapters(unittest.TestCase):
    def test_refinement_roundtrip(self):
        source=(ROOT/'outputs/frozen_candidates/F6/code/scripts/review_refinement.py').read_text(encoding='utf-8')
        mod=types.ModuleType('f7_refinement_test')
        exec(compile(keep_patch(order_patch(source)),'f7-refinement','exec'),mod.__dict__)
        evidence=[{'id':'source-a','document_id':'doc-a','text':'확인된 사실과 수치 17'}]
        draft={'title':'시험','paragraphs':[
            {'id':'original-1','text':'첫 번째 문단의 확인된 설명을 유지합니다.','sources':copy.deepcopy(evidence)},
            {'id':'original-2','text':'두 번째 문단의 잘못된 설명을 수정합니다.','sources':copy.deepcopy(evidence)}], 'tables':[]}
        memory={'draft':draft,'evidence':evidence,'compressed_sources':evidence,
                'documents':[{'id':'doc-a'}],'prepared_context':{'quality_version':2}}
        categories=['units_and_arithmetic','conflicting_basis','missing_vs_zero','causal_claims']
        def complete(llm,config,request,*args,**kwargs):
            schema=request['structured_outputs']['json']
            self.assertEqual(next(iter(schema['properties'])),'quality_checks')
            self.assertEqual(set(schema['properties']['quality_checks']['required']),set(categories))
            self.assertEqual(schema['properties']['revisions']['minItems'],2)
            result={'quality_checks':{c:{'status':'supported','reason':'원문 사실 대조','source_ids':['S1']} for c in categories},
                    'revisions':[{'paragraph_id':'P1','action':'keep'},
                                 {'paragraph_id':'P2','action':'revise','text':'두 번째 문단은 확인된 원문 사실에 맞추어 설명을 수정합니다.','source_ids':['S1'],'reason':'원문에 맞게 수정'}],
                    'additions':[],'remaining_gaps':[],
                    'information_guidance':{'explanation':'추가 확인사항 없음','needed_contents':[]}}
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(result,ensure_ascii=False)}}]}
        app=types.SimpleNamespace(lock=threading.RLock(),config=lambda:{'model':'test'},dump=lambda *args:None)
        with mocked.object(mod.llm_recovery,'complete',side_effect=complete):
            result=mod.refine(app,None,lambda messages:(100,32768),ROOT,'financial_accounts',memory,'시험 지침',{'run':{'review_level':2}},None)
        self.assertEqual(result['paragraphs'][0],draft['paragraphs'][0])
        self.assertEqual(result['paragraphs'][1]['sources'],evidence)
        self.assertIn('확인된 원문',result['paragraphs'][1]['text'])
        self.assertEqual(len(result['refinement']['quality_checks']),4)
        self.assertEqual(result['refinement']['quality_version'],2)
        self.assertEqual(draft['paragraphs'][1]['text'],'두 번째 문단의 잘못된 설명을 수정합니다.')

    def test_assessment_references_are_lossless(self):
        ns={'copy':copy};exec(HELPERS,ns)
        prior={'numeric_evidence':[{'metric':'임의 계정','value':17,'quote':'원문 17','source_ids':['S8']}],
               'tables':[{'columns':['기업','소재지','설명'],'row_records':[{'record_identity':'기업 A','label':'A'}],'source_ids':['S9']}]}
        out=ns['restore_assessment_references']({'numeric_evidence':[{'previous_index':0},{'value':29}], 'tables':[{'previous_index':0}]},prior)
        self.assertEqual(out['numeric_evidence'][0]['quote'],'원문 17')
        self.assertEqual(out['numeric_evidence'][0]['source_ids'],['S8'])
        self.assertEqual(out['tables'],prior['tables'])
        out['tables'][0]['columns'].append('추가');self.assertEqual(len(prior['tables'][0]['columns']),3)
        with self.assertRaises(ValueError):ns['restore_assessment_references']({'tables':[{'previous_index':2}]},prior)


if __name__=='__main__':unittest.main()
