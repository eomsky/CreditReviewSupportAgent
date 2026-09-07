import asyncio
import json
from pathlib import Path
import runpy
import sys

import httpx

sys.path.insert(0,str(Path(__file__).parents[1]/'training/credit_lora'))
try:
    evaluation=runpy.run_path(str(Path(sys.path[0])/'evaluate_served.py'))
finally:
    sys.path.pop(0)


def test_factor_duplicates_and_unavailable_sources_are_not_a_pass():
    row={'stage':'bundle','messages':[
        {'role':'user','content':json.dumps({'sources':{'S1':{'amount':100}},'calculations':{}})},
        {'role':'assistant','content':json.dumps({'findings':[{'factor_id':'F01'},{'factor_id':'F02'}]})}]}
    text=json.dumps({'findings':[
        {'factor_id':'F01','judgement':{'evidence_ids':['invented'],'summary':'금액 999'}},
        {'factor_id':'F01','judgement':{'evidence_ids':['S1']}}]})
    result=evaluation['assess'](row,text)
    assert result['json_valid'] is True
    assert result['factor_duplicates'] is True
    assert result['factor_set_exact'] is False
    assert result['invalid_reference_ids']==['invented']
    assert 999 in result['unsupported_numeric_candidates']


def test_absolute_stream_timeout_retains_text_and_closes_connection():
    class Slow(httpx.AsyncByteStream):
        closed=False
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n'
            await asyncio.sleep(1)
            yield b'data: [DONE]\n\n'
        async def aclose(self): self.closed=True
    stream=Slow()
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(
                lambda request:httpx.Response(200,stream=stream))) as client:
            return await evaluation['generate'](client,'https://test.invalid/v1','model',[],.03,100)
    result=asyncio.run(check())
    assert result['text']=='partial' and result['error']=='AbsoluteTimeout'
    assert result['complete'] is False and stream.closed


def test_done_without_stop_is_not_complete():
    async def check():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
                httpx.Response(200,content=b'data: [DONE]\n\n'))) as client:
            return await evaluation['generate'](client,'https://test.invalid/v1','model',[],1,100)
    result=asyncio.run(check())
    assert result['complete'] is False and result['error']=='IncompleteStream'
