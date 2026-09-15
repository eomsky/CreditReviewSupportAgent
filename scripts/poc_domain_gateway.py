"""Restricted, password-protected entry point for a local POC tunnel.

The tunnel connects to 127.0.0.1:8767; the existing app stays on 8766.
Configuration and generated credentials live only in the ignored workspace.
"""
import base64
import hmac
import json
import re
import secrets
import time
from http.cookies import SimpleCookie
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

BASE = Path(__file__).resolve().parents[1]
CONFIG = BASE/'workspace'/'poc_domain.json'
PUBLIC_ORIGIN = 'https://knbaipoc.co.kr'
MAX_BODY = 205*1024*1024

def settings():
    if not CONFIG.exists():
        CONFIG.parent.mkdir(exist_ok=True)
        CONFIG.write_text(json.dumps({'public_origin':PUBLIC_ORIGIN,'username':'poc','password':secrets.token_urlsafe(24)},indent=2),encoding='utf-8')
    value = json.loads(CONFIG.read_text(encoding='utf-8'))
    if not value.get('username') or not value.get('password'):
        raise ValueError('POC credentials required')
    return value

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass

    def fail(self,status,message,challenge=False):
        body=message.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','text/plain; charset=utf-8')
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store')
        if challenge:
            self.send_header('WWW-Authenticate','Basic realm="Credit Review POC", charset="UTF-8"')
        self.end_headers()
        if self.command!='HEAD':
            self.wfile.write(body)

    def authorized(self):
        try:
            cookie=SimpleCookie(self.headers.get('Cookie',''))
            token=cookie['poc_session'].value
            return self.server.sessions.get(token,0)>time.time()
        except (KeyError,ValueError):return False

    def redirect(self,path,cookie=None):
        self.send_response(303);self.send_header('Location',path)
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length','0')
        if cookie:self.send_header('Set-Cookie',cookie)
        self.end_headers()

    def page(self,name,error=False):
        text=(BASE/'frontend'/'portal'/name).read_text(encoding='utf-8')
        text=text.replace('<!--ERROR-->','<p class="error" role="alert">아이디 또는 비밀번호를 확인해 주세요.</p>' if error else '')
        body=text.encode('utf-8');self.send_response(401 if error else 200)
        self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY');self.end_headers()
        if self.command!='HEAD':self.wfile.write(body)

    def read_body(self):
        if self.headers.get('Transfer-Encoding','').lower()=='chunked':
            body=bytearray()
            while True:
                size=int(self.rfile.readline(128).split(b';',1)[0].strip(),16)
                if size<0 or len(body)+size>MAX_BODY:
                    raise ValueError('Too large')
                if size==0:
                    while self.rfile.readline(8192) not in (b'\r\n',b'\n',b''):
                        pass
                    return bytes(body)
                chunk=self.rfile.read(size)
                if len(chunk)!=size or self.rfile.read(2)!=b'\r\n':
                    raise ValueError('Invalid body')
                body.extend(chunk)
        length=int(self.headers.get('Content-Length','0'))
        if length<0 or length>MAX_BODY:
            raise ValueError('Too large')
        body=self.rfile.read(length)
        if len(body)!=length:
            raise ValueError('Incomplete body')
        return body

    def forward(self):
        if self.headers.get('X-Forwarded-Proto','').lower()=='http':
            self.send_response(308)
            self.send_header('Location',self.server.poc_settings['public_origin']+'/')
            self.send_header('Content-Length','0')
            self.end_headers()
            return
        path=urlsplit(self.path).path
        if self.command=='POST' and path in ('/login','/logout'):
            if self.headers.get('Origin') not in (None,self.server.poc_settings['public_origin'],'http://127.0.0.1:8767'):
                return self.fail(403,'Origin rejected')
            secure='; Secure' if self.headers.get('X-Forwarded-Proto')=='https' else ''
            if path=='/logout':
                try:self.server.sessions.pop(SimpleCookie(self.headers.get('Cookie',''))['poc_session'].value,None)
                except (KeyError,ValueError):pass
                return self.redirect('/login','poc_session=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'+secure)
            if int(self.headers.get('Content-Length','0'))>4096 or self.headers.get('Transfer-Encoding'):
                return self.fail(413,'요청이 너무 큽니다.')
            data=parse_qs(self.read_body().decode('utf-8'))
            c=self.server.poc_settings
            if not (hmac.compare_digest(data.get('username',[''])[0].encode(),c['username'].encode()) and hmac.compare_digest(data.get('password',[''])[0].encode(),c['password'].encode())):
                return self.page('login.html',error=True)
            self.server.sessions={k:v for k,v in self.server.sessions.items() if v>time.time()}
            token=secrets.token_urlsafe(32);self.server.sessions[token]=time.time()+28800
            return self.redirect('/','poc_session='+token+'; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800'+secure)
        if path=='/login' and self.command in ('GET','HEAD'):
            return self.redirect('/') if self.authorized() else self.page('login.html')
        if not self.authorized():
            return self.redirect('/login') if self.command in ('GET','HEAD') and not path.startswith('/api/') else self.fail(401,'로그인이 필요합니다.')
        if path in ('/','/index.html') and self.command in ('GET','HEAD'):
            return self.page('index.html')
        if self.command in ('GET','HEAD'):
            if path not in ('/credit-review','/api/credit-review/v1/events','/api/credit-review/v1/connection') and not re.fullmatch(r'/evidence/[0-9a-f]{64}/(?:p\d+-r\d+|c\d+)\.png',path):
                return self.fail(404,'Not found')
        elif self.command=='POST':
            if path not in {'/api/credit-review/v1/'+op for op in ('upload','state','analyze','chat','chat-settings','cancel','information-gaps','sentence-analysis','export','reset-opinions')}:
                return self.fail(404,'Not found')
            origin=self.headers.get('Origin')
            if origin not in (None,self.server.poc_settings['public_origin'],'http://127.0.0.1:8767'):
                return self.fail(403,'Origin rejected')
        else:
            return self.fail(405,'Method not allowed')
        try:
            body=self.read_body() if self.command=='POST' else None
        except (ValueError,TimeoutError):
            return self.fail(413,'파일 크기 또는 요청 형식을 확인해 주세요.')
        upstream=HTTPConnection('127.0.0.1',8766,timeout=120)
        response_started=False
        try:
            headers={}
            if body is not None:
                # Validate the public origin above, then forward as the trusted local caller.
                headers={'Content-Type':self.headers.get('Content-Type','application/json'),'Content-Length':str(len(body)),'Origin':'http://127.0.0.1:8766'}
            upstream.request(self.command,'/' if path=='/credit-review' else self.path,body=body,headers=headers)
            result=upstream.getresponse()
            self.send_response(result.status)
            for key,value in result.getheaders():
                if key.lower() in ('content-type','content-length'):
                    self.send_header(key,value)
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','same-origin')
            self.end_headers()
            response_started=True
            if self.command!='HEAD':
                while chunk:=result.read1(65536):
                    self.wfile.write(chunk);self.wfile.flush()
        except (OSError,TimeoutError):
            # Do not expose internal paths, logs, or credentials in error responses.
            if not response_started and not self.wfile.closed:
                try:self.fail(502,'POC 앱 서버가 실행 중인지 확인해 주세요.')
                except OSError:pass
        finally:
            upstream.close()

    do_GET=forward
    do_HEAD=forward
    do_POST=forward

def main():
    server=ThreadingHTTPServer(('127.0.0.1',8767),Handler)
    server.poc_settings=settings()
    server.sessions={}
    print('POC domain gateway ready at http://127.0.0.1:8767',flush=True)
    server.serve_forever()

if __name__=='__main__':
    main()
