"""Apply a source-checked paragraph patch without changing any other report content."""
import argparse, copy, hashlib, json, time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('folder'); args=ap.parse_args()
    folder=Path(args.folder); start=time.perf_counter()
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
    contract=read(folder/'review-contract.json')
    before=read(folder/'evidence-expanded-artifact.json'); after=copy.deepcopy(before)
    patch=read(folder/'verified-patch.json')
    assert patch['quality_status']=='pass' and patch['checks']
    sources={s['id']:s for s in after['sources']}
    assert patch['source_ids'] and set(patch['source_ids'])<=sources.keys()
    changed=[]
    for section in after['sections']:
        for p in section['paragraphs']:
            if p['id']==contract['target_id']:
                changed.append(p['id']);p['text']=patch['text'];p['source_ids']=patch['source_ids']
                p['sources']=[sources[sid] for sid in p['source_ids']]
    assert changed==[contract['target_id']]
    for old,new in zip(before['sections'],after['sections']):
        assert old['tables']==new['tables']
        for a,b in zip(old['paragraphs'],new['paragraphs']):
            if a['id']!=contract['target_id']:assert a==b
    save(folder/'reviewed-artifact.json',after)
    lines=[]
    for s in after['sections']:
        lines.append(s['title']);lines.extend(p['text'] for p in s['paragraphs'])
        for t in s['tables']:
            lines.extend([t['caption'],' | '.join(t['columns'])]);lines.extend(' | '.join(map(str,r)) for r in t['rows'])
    (folder/'full-output.txt').write_text('\n\n'.join(lines),encoding='utf-8')
    elapsed=read(folder/'trial/attempt-001/result.json')['elapsed_seconds']+contract.get('retrieval_seconds',0)+contract.get('initial_assembly_seconds',0)+time.perf_counter()-start
    target=contract['target_seconds']; status='pass' if elapsed<=target else 'provisional_pass' if elapsed<=target+40 else 'fail'
    result={'step':contract['step'],'version':folder.name.split('-step')[0],'status':'completed','elapsed_seconds':elapsed,'target_seconds':target,'time_status':status,'quality_status':'pass',f'allow_step{contract["step"]+1}':status!='fail','end_to_end':False,'scope':'retrieval, assembly, targeted model review and local application; preparation and human QA excluded','artifact_sha256':{n:hashlib.sha256((folder/n).read_bytes()).hexdigest() for n in ['reviewed-artifact.json','full-output.txt','verified-patch.json']}}
    save(folder/'step-result.json',result); print(json.dumps(result))

if __name__=='__main__':main()
