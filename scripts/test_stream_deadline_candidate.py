import json, threading, time, types, unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from frozen_stream_deadline_patch import patch


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        self.rfile.read(int(self.headers['Content-Length']))
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
        try:
            if self.path.startswith('/stall'):
                for _ in range(40):
                    self.wfile.write(b': heartbeat\n\n');self.wfile.flush();time.sleep(.1)
            else:
                event={'id':'test','choices':[{'delta':{'content':'ok'},'finish_reason':'stop'}]}
                self.wfile.write(('data: '+json.dumps(event)+'\n\ndata: [DONE]\n\n').encode());self.wfile.flush()
        except OSError:pass


class DeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module=types.ModuleType('candidate_stream')
        exec(patch(Path('outputs/frozen_candidates/C9/code/scripts/llm_stream.py').read_text(encoding='utf-8')),cls.module.__dict__)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=cls.server.serve_forever,daemon=True).start()
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close()
    def config(self,path):return {'base_url':f'http://127.0.0.1:{self.server.server_port}/{path}','model':'test'}
    def test_completed_stream(self):
        r=self.module.complete(self.config('ok'),{},lambda *a:None,timeout=1)
        self.assertEqual(r['choices'][0]['message']['content'],'ok')
    def test_heartbeats_do_not_extend_output_deadline(self):
        began=time.monotonic()
        with self.assertRaises(self.module.IncompleteStreamError):
            self.module.complete(self.config('stall'),{},lambda *a:None,timeout=1)
        self.assertLess(time.monotonic()-began,3)


if __name__=='__main__':unittest.main()
