import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import business_report_test as api


class RegistrationRevisionTest(unittest.TestCase):
    def test_initial_null_revision_and_existing_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            with patch.object(api.app, 'ROOT', Path(temp)), patch.object(api, 'CASES', {}), \
                 patch.object(api, 'worker'), patch.object(api.STORE, 'manifest', return_value=[]):
                server = api.app.ThreadingHTTPServer(('127.0.0.1', 0), api.Handler)
                threading.Thread(target=server.serve_forever, daemon=True).start()
                self.addCleanup(server.server_close)
                try:
                    payload = dict(case_id='new-registration', base_revision=None,
                                   documents=[{'id': 'test-document'}],
                                   target_views=['financial_accounts'],
                                   generation_prompts={'financial_accounts': [{'text': 'test'}]})
                    url = f'http://127.0.0.1:{server.server_port}/api/credit-review/v1/analyze'
                    def send():
                        return urlopen(Request(url, data=json.dumps(payload).encode(),
                                               headers={'Content-Type': 'application/json'}))
                    with send() as response:
                        self.assertEqual(json.load(response)['status'], 'running')
                    state = api.CASES[payload['case_id']]
                    state['run']['status'] = 'completed'
                    state['revision'] = 1
                    with self.assertRaises(HTTPError) as caught:
                        send()
                    self.assertEqual(caught.exception.code, 409)
                    self.assertEqual(state['revision'], 1)
                    self.assertEqual(state['run']['status'], 'completed')
                finally:
                    server.shutdown()


if __name__ == '__main__':
    unittest.main()
