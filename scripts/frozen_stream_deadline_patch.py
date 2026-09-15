"""Bound SSE stalls, including heartbeats without actual output progress."""
import ast


def patch(source):
    source=source.replace('import socket\n','import socket\nimport time\n')
    old='''        finished=threading.Event()
        def interrupt():
            while not finished.wait(.1):
                if cancel_event.is_set():
                    try: response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
                    except (AttributeError,OSError): pass
                    return
        if cancel_event:threading.Thread(target=interrupt,daemon=True).start()
        try:
            return _read(response,config,on_delta,cancel_event)
        finally:finished.set()'''
    new='''        finished=threading.Event();expired=threading.Event()
        started=time.monotonic();last_progress=[started]
        idle_limit=max(1,float(timeout))
        total_limit=max(idle_limit,float(config.get('request_deadline_seconds',900)))
        def progress(delta,text):
            last_progress[0]=time.monotonic()
            on_delta(delta,text)
        def interrupt():
            while not finished.wait(.1):
                now=time.monotonic()
                cancelled=bool(cancel_event and cancel_event.is_set())
                stalled=now-last_progress[0]>idle_limit or now-started>total_limit
                if cancelled or stalled:
                    if stalled:expired.set()
                    try: response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
                    except (AttributeError,OSError): pass
                    return
        threading.Thread(target=interrupt,daemon=True).start()
        try:
            result=_read(response,config,progress,cancel_event)
            if expired.is_set():raise IncompleteStreamError('모델 응답 대기시간 초과: 미완료 응답 폐기')
            return result
        except Exception:
            if cancel_event and cancel_event.is_set():raise GenerationCancelled()
            if expired.is_set():raise IncompleteStreamError('모델 응답 대기시간 초과: 미완료 응답 폐기') from None
            raise
        finally:finished.set()'''
    assert source.count(old)==1
    source=source.replace(old,new)
    ast.parse(source)
    return source
