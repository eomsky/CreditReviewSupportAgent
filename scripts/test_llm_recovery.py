import copy
import json
import unittest
from types import SimpleNamespace
from llm_stream import ContextLimitError,GenerationCancelled,is_context_error,IncompleteStreamError
from llm_recovery import complete,split_schema,CapacityError


def response(value,finish='stop'):
    return {'choices':[{'finish_reason':finish,'message':{'content':json.dumps(value)}}]}


class RecoveryTests(unittest.TestCase):
    def test_incomplete_stream_retries_only_once(self):
        calls=[]
        def send(*args,**kwargs):
            calls.append(1)
            raise IncompleteStreamError('interrupted')
        with self.assertRaises(IncompleteStreamError):
            complete(SimpleNamespace(complete=send),{},self.payload(),lambda *a:None,lambda m:(100,32768))
        self.assertEqual(len(calls),2)

    def test_large_output_is_partitioned_before_first_model_call(self):
        req=self.payload();req['max_tokens']=8000;calls=[]
        def send(config,request,*args,**kwargs):
            keys=list(request['structured_outputs']['json']['properties']);calls.append(keys)
            return response({k:'완료' for k in keys})
        result=complete(SimpleNamespace(complete=send),{},req,lambda *a:None,lambda m:(1000,4000))
        self.assertEqual(calls,[['a'],['b']])
        self.assertEqual(json.loads(result['choices'][0]['message']['content']),{'a':'완료','b':'완료'})

    def payload(self):
        return {'messages':[{'role':'system','content':'지침'},{'role':'user','content':'{}'}],
                'max_tokens':2048,'structured_outputs':{'json':{'type':'object','properties':{'a':{'type':'string'},'b':{'type':'string'}},'required':['a','b'],'additionalProperties':False}}}

    def test_truncation_partitions_and_merges_without_repeating_completed_part(self):
        calls=[]
        def send(config,request,*args,**kwargs):
            keys=list(request['structured_outputs']['json']['properties']);calls.append(keys)
            return response({k:k+'완결' for k in keys},'length' if len(keys)>1 else 'stop')
        result=complete(SimpleNamespace(complete=send),{},self.payload(),lambda *a:None,lambda m:(1000,3560))
        self.assertEqual(json.loads(result['choices'][0]['message']['content']),{'a':'a완결','b':'b완결'})
        self.assertEqual(calls,[['a','b'],['a'],['b']])

    def test_http_context_error_adjusts_budget_and_retries(self):
        budgets=[]
        def send(config,request,*args,**kwargs):
            budgets.append(request['max_tokens'])
            if len(budgets)==1:raise ContextLimitError()
            return response({'a':'ok','b':'ok'})
        complete(SimpleNamespace(complete=send),{},self.payload(),lambda *a:None,lambda m:(1000,8000))
        self.assertEqual(budgets,[2048,1024])

    def test_input_compression_keeps_all_source_ids_and_does_not_mutate_input(self):
        req=self.payload();req['messages'][-1]['content']=json.dumps({'sources':[{'id':'S1','text':'원문'*2000},{'id':'S2','text':'근거'*2000}]})
        original=copy.deepcopy(req)
        def count(messages):return (len(messages[-1]['content']),4000)
        def send(config,request,*args,**kwargs):
            self.assertEqual([s['id'] for s in json.loads(request['messages'][-1]['content'])['sources']],['S1','S2'])
            return response({'a':'ok','b':'ok'})
        complete(SimpleNamespace(complete=send),{},req,lambda *a:None,count)
        self.assertEqual(req,original)

    def test_review_partition_covers_each_paragraph_once(self):
        schema={'type':'array','minItems':4,'maxItems':4,'items':{'type':'object','properties':{'paragraph_id':{'type':'string','enum':['P1','P2','P3','P4']}}}}
        parts=split_schema(schema)
        self.assertEqual([p['items']['properties']['paragraph_id']['enum'] for p in parts],[['P1','P2'],['P3','P4']])

    def test_cancellation_and_unrelated_errors_are_not_retried(self):
        for error in (GenerationCancelled(),ValueError('other')):
            calls=[]
            def send(*args,**kwargs):calls.append(1);raise error
            with self.assertRaises(type(error)):
                complete(SimpleNamespace(complete=send),{},self.payload(),lambda *a:None,lambda m:(1,8000))
            self.assertEqual(len(calls),1)

    def test_context_error_classification(self):
        self.assertTrue(is_context_error('maximum context length is 32768'))
        self.assertFalse(is_context_error('Unauthorized'))

    def test_unrecoverable_request_is_bounded(self):
        def send(*args,**kwargs):raise ContextLimitError()
        with self.assertRaises(CapacityError):
            complete(SimpleNamespace(complete=send),{},self.payload(),lambda *a:None,lambda m:(1,8000))


if __name__=='__main__':unittest.main()
