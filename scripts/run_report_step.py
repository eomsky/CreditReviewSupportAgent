"""Token-preflight and run one already-prepared report experiment."""
import argparse,json,urllib.request
from pathlib import Path
from step_trial import initialize,trial

def main():
    a=argparse.ArgumentParser();a.add_argument('folder');args=a.parse_args()
    root=Path(__file__).resolve().parents[1];p=Path(args.folder)
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    save=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    r=read(p/'generation.request.json');c=read(root/'workspace/llm_connection.json')
    ep=c['base_url'].rstrip('/');ep=ep[:-3] if ep.endswith('/v1') else ep
    headers={'Authorization':'Bearer '+c['api_key'],'Content-Type':'application/json'}
    models=json.load(urllib.request.urlopen(urllib.request.Request(ep+'/v1/models',headers=headers),timeout=20))['data']
    limit=min(65536,int(next(m.get('max_model_len',32768) for m in models if m['id']==c['model'])))
    count=json.load(urllib.request.urlopen(urllib.request.Request(ep+'/tokenize',data=json.dumps({'model':c['model'],'messages':r['messages'],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}).encode(),headers=headers),timeout=30))['count']
    r['max_tokens']=min(8000,limit-count-512)
    if r['max_tokens']<3000:raise ValueError('Insufficient context budget')
    save(p/'generation.request.json',r);save(p/'budget-audit.json',{'input':count,'output':r['max_tokens'],'limit':limit,'reserve':512})
    print('preflight',count,flush=True)
    contract=read(p/'review-contract.json') if (p/'review-contract.json').exists() else read(p/'reuse-contract.json') if (p/'reuse-contract.json').exists() else {}
    initialize(p/'trial',p/'generation.request.json',contract.get('target_seconds',90))
    print(json.dumps(trial(p/'trial',root/'outputs/frozen_candidates/C20.4-step2-r1',timeout=180),ensure_ascii=False))

if __name__=='__main__':main()
