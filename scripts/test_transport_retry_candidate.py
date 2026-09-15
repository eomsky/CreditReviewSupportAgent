import types,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from http.client import RemoteDisconnected
from urllib.error import HTTPError
from frozen_transport_retry_patch import patch as transform

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.module=types.ModuleType('transport_candidate')
        exec(transform(Path('outputs/frozen_candidates/C11/code/scripts/llm_stream.py').read_text(encoding='utf-8')),self.module.__dict__)
        self.config={'base_url':'http://localhost/v1','model':'test'}
    def test_before_headers_is_retryable(self):
        with patch.object(self.module,'urlopen',side_effect=RemoteDisconnected()):
            with self.assertRaises(self.module.IncompleteStreamError):self.module.complete(self.config,{},lambda *a:None)
    def test_interrupted_body_is_never_accepted(self):
        response=MagicMock()
        with patch.object(self.module,'urlopen',return_value=response),patch.object(self.module,'_read',side_effect=RemoteDisconnected()):
            with self.assertRaises(self.module.IncompleteStreamError):self.module.complete(self.config,{},lambda *a:None)
    def test_auth_error_not_retried(self):
        with patch.object(self.module,'urlopen',side_effect=HTTPError('local',401,'Unauthorized',{},None)):
            with self.assertRaises(HTTPError):self.module.complete(self.config,{},lambda *a:None)

if __name__=='__main__':unittest.main()
