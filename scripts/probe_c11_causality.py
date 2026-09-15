"""Replay one recorded review request; explicitly not an end-to-end test."""
import copy,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CODE=ROOT/'outputs/frozen_candidates/C11-assembly-preflight'
sys.path[:0]=[str(CODE/'code/scripts'),str(CODE/'harness')]
import llm_stream,review_refinement
from frozen_causal_support_patch import RULE
number=sys.argv[1] if len(sys.argv)>1 else '017'
OUT=ROOT/'outputs/frozen_candidates'/('C11-causality-probe-'+number)
OUT.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
request=read(ROOT/'outputs/frozen_candidates/C10/calls'/f'{number}.request.json')
body=json.loads(request['messages'][1]['content'])
causal=review_refinement.schema_for(body['draft'],body['compressed_sources'])['properties']['quality_checks']['properties']['causal_claims']
request['structured_outputs']['json']['properties']['quality_checks']['properties']['causal_claims']=causal
request['messages'][0]['content']+='\n'+RULE
cfg=read(ROOT/'workspace/llm_connection.json')
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
save('request.json',request)
began=time.monotonic()
response=llm_stream.complete(cfg,request,lambda *args:None,timeout=600)
save('response.json',response)
result=json.loads(response['choices'][0]['message']['content'])
save('result.json',{'end_to_end':False,'elapsed_seconds':time.monotonic()-began,'usage':response.get('usage'),'finish_reason':response['choices'][0]['finish_reason'],'review':result})
print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
