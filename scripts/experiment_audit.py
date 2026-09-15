"""Read-only structural checks for experimental outputs; flags are not fact verification."""
import json,re
from pathlib import Path
from experiment_versions import OUT,dump

def sections(result):
    value=result.get('sections')
    return list(value.values()) if isinstance(value,dict) else value if isinstance(value,list) else [result]

def audit(folder):
    findings=[];paragraphs=0;characters=0;cells=0;empty=0
    for path in folder.glob('*.result.json'):
        result=json.loads(path.read_text(encoding='utf-8'))
        sourcepath=folder/(path.name.replace('.result.json','.sources.json'))
        ids={f'S{i+1}' for i,_ in enumerate(json.loads(sourcepath.read_text(encoding='utf-8')))} if sourcepath.exists() else set()
        for si,s in enumerate(sections(result)):
            for p in s.get('paragraphs',[]):
                paragraphs+=1;characters+=len(p['text'])
                if not set(p.get('source_ids',[]))<=ids:findings.append({'file':path.name,'kind':'invalid_source_id'})
                if re.search(r'\bS\d+\b',p['text']):findings.append({'file':path.name,'kind':'internal_id_in_text'})
            for ti,t in enumerate(s.get('tables',[])):
                width=len(t['columns']);seen={}
                customer=width==6 and any('매출처' in str(c) for c in t['columns'])
                for ri,row in enumerate(t['rows']):
                    cells+=len(row);empty+=sum(c is None or c=='' for c in row)
                    if len(row)!=width:findings.append({'file':path.name,'kind':'row_width','table':ti,'row':ri})
                    segments=[row[:3],row[3:]] if customer else [row]
                    for side,segment in enumerate(segments):
                        if not segment or segment[0] in [None,'','합계','상기 외']:continue
                        key=(side,json.dumps(segment,ensure_ascii=False))
                        if key in seen:findings.append({'file':path.name,'kind':'duplicate_detail','table':ti,'rows':[seen[key],ri],'side':side})
                        seen[key]=ri
    results=json.loads((folder/'results.json').read_text(encoding='utf-8'))
    tokens=sum((s.get('usage') or {}).get('completion_tokens',0) for s in results['steps'])
    result={'status':results['status'],'elapsed_seconds':results.get('elapsed_seconds'),'paragraphs':paragraphs,'body_characters':characters,'cells':cells,'empty_cells':empty,'output_tokens':tokens,'structural_findings':findings,'note':'빈칸은 오류로 단정하지 않음. 출처·단위·인과 정확성은 별도 검증 필요.'}
    dump(folder/'audit.json',result);return result

if __name__=='__main__':
    for folder in OUT.glob('v*'):
        if (folder/'results.json').exists():print(folder.name,audit(folder))
