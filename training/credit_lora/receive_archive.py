"""Temporary authenticated one-file transfer into the user's Colab runtime."""
import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler,HTTPServer
import json
import os
from pathlib import Path

p=argparse.ArgumentParser(); p.add_argument('target',type=Path); p.add_argument('--sha256',required=True)
p.add_argument('--connection',type=Path,default=Path('/content/credit_llm_server/llm_connection.json'))
p.add_argument('--port',type=int,default=8002); a=p.parse_args()
key=json.loads(a.connection.read_text())['api_key']

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_POST(self):
        if self.path!='/archive' or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+key):
            self.send_error(403); return
        length=int(self.headers.get('Content-Length','0'))
        if not 0<length<=64*1024*1024: self.send_error(413); return
        tmp=a.target.with_suffix('.transfer.tmp'); hasher=hashlib.sha256(); remaining=length
        self.connection.settimeout(60)
        with tmp.open('wb') as f:
            while remaining:
                block=self.rfile.read(min(1024*1024,remaining))
                if not block: raise EOFError('Incomplete transfer')
                f.write(block); hasher.update(block); remaining-=len(block)
        if not hmac.compare_digest(hasher.hexdigest(),a.sha256):
            tmp.unlink(); self.send_error(422); return
        os.replace(tmp,a.target)
        data=json.dumps({'bytes':length,'sha256':hasher.hexdigest()}).encode()
        self.send_response(200); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

HTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
