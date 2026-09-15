"""Read OpenAI-compatible SSE incrementally without buffering the full answer."""
import json
import threading
import socket
from urllib.request import Request,urlopen
from urllib.error import HTTPError

class ContextLimitError(ValueError):
    pass

def is_context_error(message):
    text=str(message).lower()
    return any(term in text for term in ('maximum context length','context length exceeded','max_model_len','maximum number of tokens','max_tokens is too large','max_completion_tokens is too large'))

class GenerationCancelled(Exception):
    pass

class IncompleteStreamError(ConnectionError):
    pass

def complete(config,payload,on_delta,timeout=100,cancel_event=None):
    payload={**payload,'stream':True,'stream_options':{'include_usage':True}}
    req=Request(config['base_url'].rstrip('/')+'/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+config.get('api_key',''),'Content-Type':'application/json'})
    text='';usage=None;finish=None;response_id=None;done=False
    if cancel_event and cancel_event.is_set():raise GenerationCancelled()
    try:
        opened=urlopen(req,timeout=timeout)
    except HTTPError as error:
        if error.code in (400,413,422) and is_context_error(error.read(65536).decode('utf-8',errors='replace')):
            raise ContextLimitError('모델 문맥 한도 초과') from None
        raise
    with opened as response:
        finished=threading.Event()
        def interrupt():
            while not finished.wait(.1):
                if cancel_event.is_set():
                    try: response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
                    except (AttributeError,OSError): pass
                    return
        if cancel_event:threading.Thread(target=interrupt,daemon=True).start()
        try:
            return _read(response,config,on_delta,cancel_event)
        finally:finished.set()

def _read(response,config,on_delta,cancel_event):
    text='';usage=None;finish=None;response_id=None;done=False
    try:
        for line in response:
            if cancel_event and cancel_event.is_set():raise GenerationCancelled()
            if not line.startswith(b'data:'):continue
            raw=line[5:].strip()
            if raw==b'[DONE]':done=True;break
            event=json.loads(raw)
            if event.get('error'):
                if is_context_error(event['error']):raise ContextLimitError('모델 문맥 한도 초과')
                raise ValueError('모델 스트림 오류')
            response_id=event.get('id',response_id);usage=event.get('usage') or usage
            for choice in event.get('choices',[]):
                delta=choice.get('delta',{}).get('content') or ''
                if delta:text+=delta;on_delta(delta,text)
                finish=choice.get('finish_reason') or finish
    except Exception:
        if cancel_event and cancel_event.is_set():raise GenerationCancelled()
        raise
    if cancel_event and cancel_event.is_set():raise GenerationCancelled()
    if not done or not finish:raise IncompleteStreamError('응답 스트림이 완료되기 전에 끊어졌습니다.')
    return {'id':response_id,'model':config['model'],'usage':usage,'choices':[{'message':{'role':'assistant','content':text},'finish_reason':finish}]}
