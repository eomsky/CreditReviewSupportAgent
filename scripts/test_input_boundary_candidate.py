import copy
import json
import unittest
from frozen_input_boundary import fit


class InputBoundaryTest(unittest.TestCase):
    def test_complete_units_and_header_dependencies_and_immutability(self):
        sources=[{'id':'S1','text':'a'*200,'header_source_id':'S3'},
                 {'id':'S2','text':'b'*3000}, {'id':'S3','text':'period and unit'}]
        body={'sources':sources,'draft':{'source_ids':['S1']}}
        request={'max_tokens':100,'messages':[{'role':'user','content':json.dumps(body)}],
                 'structured_outputs':{'json':{'properties':{'source_ids':{'items':{'enum':['S1','S2','S3']}}}}}}
        original=copy.deepcopy(request)
        out,audit=fit(request,lambda messages:(len(messages[-1]['content']),1200))
        selected=json.loads(out['messages'][-1]['content'])['sources']
        self.assertEqual([s['id'] for s in selected],['S1','S3'])
        self.assertEqual(selected[0],sources[0])
        self.assertEqual(request,original)
        self.assertLessEqual(audit['input_tokens'],audit['input_ceiling'])
        self.assertEqual(out['structured_outputs']['json']['properties']['source_ids']['items']['enum'],['S1','S3'])

    def test_oversized_indispensable_source_is_not_truncated(self):
        text='original table '*300
        req={'max_tokens':100,'messages':[{'role':'user','content':json.dumps({'sources':[{'id':'S1','text':text}], 'draft':{'source_ids':['S1']}})}]}
        out,audit=fit(req,lambda messages:(len(messages[-1]['content']),1200))
        self.assertEqual(audit['status'],'indispensable_context_requires_partition')
        self.assertEqual(json.loads(out['messages'][-1]['content'])['sources'][0]['text'],text)

    def test_required_document_coverage_preserved(self):
        body={'documents':[{'id':'doc','required':True}],
              'sources':[{'id':'S1','document_id':'doc','text':'required'}, {'id':'S2','text':'x'*3000}]}
        req={'max_tokens':100,'messages':[{'role':'user','content':json.dumps(body)}]}
        out,audit=fit(req,lambda messages:(len(messages[-1]['content']),1200))
        self.assertEqual([s['id'] for s in json.loads(out['messages'][-1]['content'])['sources']],['S1'])


if __name__=='__main__':unittest.main()
