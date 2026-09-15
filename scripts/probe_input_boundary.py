"""Read-only token-budget check on a saved request; never calls generation."""
import json
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from frozen_input_boundary import fit

root=Path(__file__).resolve().parents[1]
request_path=Path(sys.argv[1])
output=Path(sys.argv[2])
if output.exists():raise ValueError('Preserve existing measurement')
configuration=json.loads((root/'workspace/llm_connection.json').read_text(encoding='utf-8-sig'))
request=json.loads(request_path.read_text(encoding='utf-8-sig'))
endpoint=configuration['base_url'].rstrip('/')
if endpoint.endswith('/v1'):endpoint=endpoint[:-3]
counts=[]
def count(messages):
    payload={'model':configuration['model'],'messages':messages,'add_generation_prompt':True,
             'chat_template_kwargs':{'enable_thinking':False}}
    req=Request(endpoint+'/tokenize',data=json.dumps(payload).encode(),headers={
        'Authorization':'Bearer '+configuration['api_key'],'Content-Type':'application/json'})
    with urlopen(req,timeout=60) as response:result=json.load(response)
    counts.append(result['count'])
    return result['count'],min(result.get('max_model_len',32768),32768)
started=time.monotonic()
reserve=int(sys.argv[3]) if len(sys.argv)>3 else None
if reserve is not None:request['max_tokens']=reserve
selected,audit=fit(request,count)
output.mkdir(parents=True,exist_ok=False)
(output/'selected-request.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),encoding='utf-8')
audit.update(end_to_end=False,generation_called=False,tokenizer_calls=len(counts),
             elapsed_seconds=round(time.monotonic()-started,3),source_request=str(request_path))
(output/'audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False))
