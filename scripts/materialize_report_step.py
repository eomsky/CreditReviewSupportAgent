"""Materialize a completed report trial without another generation call."""
import argparse
import json
import time
from pathlib import Path
import prepared_context

read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
save = lambda p,d: p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('folder');args=parser.parse_args()
    folder=Path(args.folder);start=time.perf_counter()
    trial=read(folder/'trial/attempt-001/result.json')
    response=read(folder/'trial/attempt-001/response.json')
    if response['choices'][0]['finish_reason'] != 'stop': raise ValueError('Incomplete model output')
    body=json.loads(response['choices'][0]['message']['content'])
    contract=read(folder/'reuse-contract.json') if (folder/'reuse-contract.json').exists() else {'step':13,'part':1,'target_seconds':90}
    request=read(folder/'generation.request.json')
    expected=request['structured_outputs']['json']['properties']['sections']['items']['properties']['title']['enum']
    assert [s['title'] for s in body['sections']] == expected, 'Missing, repeated or reordered section'
    if (folder/'reuse-catalog.json').exists():
        catalog=read(folder/'reuse-catalog.json');selected=[]
        required=[set(contract['roles_by_section'][title]) for title in expected] if 'roles_by_section' in contract else [{'establishment','history','management','ownership','affiliates'}, {'business_model','sales','customers','purchases','market'}]
        for section,roles in zip(body['sections'],required):
            assert {p['role'] for p in section['paragraphs']}==roles, 'Incomplete reuse coverage'
            assert len(section['paragraphs'])==len(roles), 'Repeated role'
            ids=[p['reuse_id'] for p in section['paragraphs']]
            nonempty=[k for k in ids if k]
            assert len(nonempty)==len(set(nonempty)), 'Duplicate paragraph'
            if not contract.get('allow_new_paragraphs'):assert all(ids)
            selected.extend(section['paragraphs'])
            section['paragraphs']=[dict(catalog[p['reuse_id']],heading='') if p['reuse_id'] else dict(p,heading='') for p in section['paragraphs']]
        save(folder/'reuse-selection.json',{'selected':selected,'reused_text_and_sources_preserved':True,'new_paragraph_count':sum(not p['reuse_id'] for p in selected)})
    sources=read(folder/'original-source-archive.json');aliases={s['id']:s for s in sources}
    assert len(aliases)==len(sources)
    if (folder/'table-fixtures.json').exists():
        if body.pop('table_source_check') != 'supported':raise ValueError('Model rejected source table')
        fixtures=read(folder/'table-fixtures.json')
        for section in body['sections']:
            section['tables']=fixtures[section['title']]
            for table in section['tables']:
                assert set(table['source_ids']) <= aliases.keys()
                table['after_paragraph_index']=min(table['after_paragraph_index'],len(section['paragraphs'])-1)
    else:
        prepared_context.apply(body,read(folder/'preparation.json'),aliases)
    lines=[]
    for si,section in enumerate(body['sections']):
        lines.append(section['title'])
        for pi,p in enumerate(section['paragraphs']):
            assert p['source_ids'] and set(p['source_ids']) <= aliases.keys()
            p['id']=f'report-part{contract["part"]}-s{si+1}-p{pi+1}'
            p['sources']=[aliases[sid] for sid in p['source_ids']]
            lines.extend([p.get('heading',''),p['text']])
        for table in section['tables']:
            assert all(len(row)==len(table['columns']) for row in table['rows'])
            lines.extend([table['caption'],' | '.join(table['columns'])])
            lines.extend(' | '.join(str(c) for c in row) for row in table['rows'])
    body['sources']=sources
    save(folder/'materialized-artifact.json',body)
    (folder/'full-output.txt').write_text('\n\n'.join(lines),encoding='utf-8')
    elapsed=trial['elapsed_seconds']+time.perf_counter()-start+contract.get('retrieval_seconds',0)
    result={'step':contract['step'],'version':folder.name.split('-step')[0],'status':'completed','elapsed_seconds':elapsed,
            'target_seconds':90,'time_status':'pass' if elapsed<=90 else 'provisional_pass' if elapsed<=130 else 'fail',
            'quality_status':'unassessed',f'allow_step{contract["step"]+1}':False,'end_to_end':False,
            'scope':'warm report area generation and materialization; retrieval and preparation excluded'}
    save(folder/'step-result.json',result);print(json.dumps(result))

if __name__=='__main__':main()
