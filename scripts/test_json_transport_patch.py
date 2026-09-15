import json
import unittest
import importlib.util
import sys
from unittest.mock import patch as mock_patch
from pathlib import Path
from types import SimpleNamespace
from frozen_json_transport_patch import patch


class JsonTransportTests(unittest.TestCase):
    def run_response(self, content):
        source=Path('outputs/frozen_candidates/C6/code/scripts/llm_recovery.py').read_text(encoding='utf-8')
        scope={}
        spec=importlib.util.spec_from_file_location('llm_stream','outputs/frozen_candidates/C6/code/scripts/llm_stream.py')
        stream=importlib.util.module_from_spec(spec);spec.loader.exec_module(stream)
        with mock_patch.dict(sys.modules,{'llm_stream':stream}):
            exec(compile(patch(source),'<json-recovery>','exec'),scope)
        response={'choices':[{'finish_reason':'stop','message':{'content':content}}]}
        llm=SimpleNamespace(complete=lambda *a,**k:response)
        request={'messages':[{'content':'{}'}],'max_tokens':1000,'structured_outputs':{'json':{'type':'object'}}}
        return scope['complete'](llm,{},request,None,lambda _: (100,32768))

    def test_real_failed_response_restores_exact_values(self):
        response=json.loads(Path('outputs/frozen_candidates/C6/run/summary_2.preparation.response.json').read_text(encoding='utf-8'))
        text=response['choices'][0]['message']['content']
        expected=json.loads(text,strict=False)
        result=self.run_response(text)
        self.assertEqual(json.loads(result['choices'][0]['message']['content']),expected)

    def test_other_malformed_response_is_not_silently_repaired(self):
        with self.assertRaises(json.JSONDecodeError): self.run_response('{"v":')


if __name__=='__main__':unittest.main()
