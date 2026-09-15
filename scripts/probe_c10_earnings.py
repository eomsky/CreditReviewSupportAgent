"""Partial actual-model test of role slots. Never an end-to-end benchmark."""
import json,sys,time,types,threading,runpy
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[1]
CODE=ROOT/'outputs/frozen_candidates/C10-assembly-preflight'
sys.path[:0]=[str(CODE/'code/scripts'),str(CODE/'harness')]
import llm_stream
prepared_context=types.ModuleType('probe_prepared')
transform=runpy.run_path(str(ROOT/'scripts/frozen_earnings_slots_patch.py'))['patch']
exec(transform((ROOT/'outputs/frozen_candidates/C9/code/scripts/prepared_context.py').read_text(encoding='utf-8')),prepared_context.__dict__)
OUT=ROOT/'outputs/frozen_candidates'/('C10-earnings-probe'+(sys.argv[1] if len(sys.argv)>1 else ''))
OUT.mkdir(exist_ok=False)
cfg=json.loads((ROOT/'workspace/llm_connection.json').read_text(encoding='utf-8-sig'))
def dump(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def token_count(messages):
    req=Request(cfg['base_url'].removesuffix('/v1')+'/tokenize',data=json.dumps({'model':cfg['model'],'messages':messages,'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}).encode(),headers={'Authorization':'Bearer '+cfg['api_key'],'Content-Type':'application/json'})
    with urlopen(req,timeout=60) as r:d=json.load(r)
    return d['count'],d.get('max_model_len',32768)
app=types.SimpleNamespace(BASE=OUT,config=lambda:cfg,dump=dump,lock=threading.RLock())
old=ROOT/'outputs/frozen_candidates/C9/run'
sources=json.loads((old/'profitability.evidence.json').read_text(encoding='utf-8'))
request=json.loads((old/'profitability.preparation.request.json').read_text(encoding='utf-8'))
manifest=json.loads(request['messages'][1]['content'])['documents']
began=time.monotonic()
packet=prepared_context.prepare(app,llm_stream,token_count,OUT,'profitability',sources,manifest,None,'',None,None,[],fixed=True)
result={'end_to_end':False,'elapsed_seconds':time.monotonic()-began,'rows':packet['numeric_evidence'],'arithmetic':packet['arithmetic_checks']}
dump(OUT/'result.json',result)
print(json.dumps(result,ensure_ascii=False,indent=2))
