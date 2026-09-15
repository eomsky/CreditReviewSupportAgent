"""Restore an encrypted Colab connection after verifying its authenticated model."""
import argparse,base64,json,urllib.request
from pathlib import Path
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
root=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('sealed',type=Path);a=p.parse_args()
key=serialization.load_pem_private_key((root/'workspace/colab_reconnect_private.pem').read_bytes(),password=None)
token=a.sealed.read_text().strip().split('=',1)[-1] if a.sealed.read_text().strip().startswith('SESSION_CONNECTION=') else a.sealed.read_text().strip()
config=json.loads(key.decrypt(base64.b64decode(token),padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None)))
if config['model']!='google/gemma-4-31B-it' or config['context_tokens']!=65536:raise ValueError('Server configuration differs')
url=config['base_url'].rstrip('/')+'/models'
response=json.load(urllib.request.urlopen(urllib.request.Request(url,headers={'Authorization':'Bearer '+config['api_key']}),timeout=15))
model=next(m for m in response['data'] if m['id']==config['model'])
if model.get('max_model_len')!=65536:raise ValueError('Model context mismatch')
(root/'workspace/llm_connection.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
print(json.dumps({'authenticated_health':'pass','model':model['id'],'context_tokens':model['max_model_len']}))
