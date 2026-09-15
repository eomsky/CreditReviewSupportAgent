"""Read health and diagnose schema errors without printing endpoint credentials."""
import json,re,urllib.request,urllib.error,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=root/'outputs/step_trials/C20.9s-step2-r3'
config=json.loads((root/'workspace/llm_connection.json').read_text(encoding='utf-8-sig'))
base=config['base_url'].rstrip('/');base=base[:-3] if base.endswith('/v1') else base
headers={'Authorization':'Bearer '+config['api_key'],'Content-Type':'application/json'}
report={}
try:
    raw=urllib.request.urlopen(urllib.request.Request(base+'/metrics',headers=headers),timeout=15).read().decode()
    report['requests']=[line for line in raw.splitlines() if not line.startswith('#') and any(s in line for s in ('num_requests_running','num_requests_waiting'))]
except Exception as exc:report['metrics_error']=type(exc).__name__
if '--health-only' in sys.argv:
    print(json.dumps(report,ensure_ascii=False));sys.exit(0)
# Tiny diagnostic completion with the exact schema, so an unsupported schema is visible.
request=json.loads((folder/'refinement.request.json').read_text());request['messages']=[{'role':'user','content':'Return JSON.'}];request['max_tokens']=1;request['stream']=False
try:
    response=urllib.request.urlopen(urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(request).encode(),headers=headers),timeout=30)
    report['schema_probe_http']=response.status
except urllib.error.HTTPError as exc:
    report['schema_probe_http']=exc.code
    text=exc.read().decode(errors='replace').replace(config['api_key'],'[redacted]').replace(config['base_url'],'[endpoint]')
    report['error']=re.sub(r'https?://\S+','[endpoint]',text)[:1500]
except Exception as exc:report['schema_probe_error']=type(exc).__name__
(folder/'diagnostic.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False))
