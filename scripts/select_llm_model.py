"""Select an already served base model or detachable adapter; never merge weights."""
import argparse
import json
import os
from pathlib import Path
import httpx
from credit_review.store import atomic_json

p=argparse.ArgumentParser()
p.add_argument('model',nargs='?',help='Exact served model/adapter ID; omit to list')
p.add_argument('--workspace',type=Path,default=Path(os.environ.get('CREDIT_WORKSPACE','workspace')))
a=p.parse_args(); path=a.workspace/'llm_connection.json'
config=json.loads(path.read_text(encoding='utf-8'))
headers={'Authorization':'Bearer '+config['api_key']} if config.get('api_key') else {}
with httpx.Client(timeout=15) as client:
    reply=client.get(config['base_url'].rstrip('/')+'/models',headers=headers)
    reply.raise_for_status()
models={m['id']:m for m in reply.json()['data']}
if not a.model:
    print(json.dumps({'selected':config.get('model'),'available':list(models)},ensure_ascii=False))
else:
    if a.model not in models: raise SystemExit('Requested model/adapter is not served')
    override=os.environ.get('LLM_MODEL')
    if override and override!=a.model:
        raise SystemExit('LLM_MODEL environment overrides the connection file; change that explicit override first')
    config['model']=a.model
    if models[a.model].get('max_model_len'): config['context_tokens']=models[a.model]['max_model_len']
    atomic_json(path,config); path.chmod(0o600)
    print('Selected:',a.model)
