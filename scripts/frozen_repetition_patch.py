"""Abort degenerate streams early and reuse bounded schema-partition recovery."""
import ast

HELPERS='''
class DegenerateOutputError(ValueError):
    pass

def degenerate_tail(text):
    tail=''.join(text[-4096:].split())
    if len(tail)<512:return False
    for width in range(1,33):
        count=max(64,(512+width-1)//width)
        if width*count>len(tail):continue
        unit=tail[-width:]
        if tail.endswith(unit*count):return True
    return False

'''

def stream_patch(source):
    source=source.replace('class ContextLimitError(ValueError):',HELPERS+'class ContextLimitError(ValueError):',1)
    old="                if delta:text+=delta;on_delta(delta,text)"
    assert source.count(old)==1
    source=source.replace(old,"                if delta:\n                    text+=delta\n                    if degenerate_tail(text):\n                        error=DegenerateOutputError('의미 없는 반복 출력 감지');error.partial_text=text\n                        raise error\n                    on_delta(delta,text)")
    ast.parse(source);return source

def recovery_patch(source):
    source=source.replace('from llm_stream import ContextLimitError, IncompleteStreamError','from llm_stream import ContextLimitError, IncompleteStreamError, DegenerateOutputError')
    source=source.replace('        except IncompleteStreamError:',"        except DegenerateOutputError:\n            notify('반복 출력 감지: 해당 응답을 폐기하고 생성 단위 분할')\n            response=None\n        except IncompleteStreamError:",1)
    source=source.replace("        if response['choices'][0].get('finish_reason')!='length':return response", "        if response is not None and response['choices'][0].get('finish_reason')!='length':return response")
    source=source.replace("        notify('응답 길이 초과: 잘린 응답을 폐기하고 생성 단위 조정')", "        if response is not None:notify('응답 길이 초과: 잘린 응답을 폐기하고 생성 단위 조정')")
    source=source.replace("        if req['max_tokens']<available:","        if response is not None and req['max_tokens']<available:")
    ast.parse(source);return source
