"""Materialize human/source-reviewed depth additions; preserve all earlier content."""
import argparse,copy,hashlib,json,time
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('folder');a=ap.parse_args();folder=Path(a.folder);start=time.perf_counter()
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
    c=read(folder/'review-contract.json');approval=read(folder/'quality-review.json');assert approval['quality_status']=='pass_for_additions'
    additions=read(folder/'approved-additions.json');assert set(additions)==set(c['roles'])
    before=read(folder/'source-artifact.json');body=copy.deepcopy(before);report=body.get('report',body)
    sources={s['id']:s for s in report['sources']};section=next(s for s in report['sections'] if s['title']==c['section'])
    for role,p in additions.items():
        assert p['source_ids'] and set(p['source_ids'])<=sources.keys()
        assert 'source_ids' not in p['text'] and 'contribution' not in p['text']
        section['paragraphs'].append({'id':folder.name+'-'+role,'heading':'','text':p['text'],'source_ids':p['source_ids'],'sources':[sources[s] for s in p['source_ids']]})
    original=before.get('report',before)
    for old,new in zip(original['sections'],report['sections']):
        assert old['tables']==new['tables'];assert old['paragraphs']==new['paragraphs'][:len(old['paragraphs'])]
    if 'views' in before:assert before['views']==body['views']
    assert len({p['id'] for s in report['sections'] for p in s['paragraphs']})==sum(len(s['paragraphs']) for s in report['sections'])
    save(folder/'integrated-output.json',body);save(folder/'reviewed-artifact.json',report)
    trial=read(folder/'trial/attempt-001/result.json');elapsed=trial['elapsed_seconds']+time.perf_counter()-start+c.get('initial_preparation_seconds',0)+c.get('prior_attempt_seconds',0)
    save(folder/'depth-result.json',{'version':folder.name,'elapsed_seconds':elapsed,'end_to_end':False,'scope':'focused generation/preparation/application, human QA excluded','added_characters':sum(len(p['text']) for p in additions.values()),'quality_status':'pass_for_additions_only','whole_report_quality_status':'unassessed','artifact_sha256':hashlib.sha256((folder/'integrated-output.json').read_bytes()).hexdigest()})
    print(json.dumps(read(folder/'depth-result.json')))

if __name__=='__main__':main()
