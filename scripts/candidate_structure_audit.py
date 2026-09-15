"""Read-only candidate diagnostics. Passing structural checks is not semantic QA."""
import json, sys, re
from pathlib import Path


def audit(state):
    findings=[]
    sections=list(state.get('views',{}).items())+[(f'report:{i}',s) for i,s in enumerate(state.get('report',{}).get('sections',[]))]
    counts={'sections':len(sections),'tables':0,'unresolved_tables':0}
    for key,section in sections:
        for ti,table in enumerate(section.get('tables',[])):
            counts['tables']+=1
            location={'section':key,'table':ti,'caption':table.get('caption','')}
            columns=table.get('columns',[]);rows=table.get('rows',[])
            def flag(code,detail):findings.append({**location,'code':code,'detail':detail})
            if not columns:flag('missing_columns','No column definitions')
            bad=[i for i,r in enumerate(rows) if len(r)!=len(columns)]
            if bad:flag('ragged_rows',bad)
            references=[{'row':ri,'column':ci,'value':v} for ri,r in enumerate(rows) for ci,v in enumerate(r)
                        if isinstance(v,str) and re.fullmatch(r'S\d+\s*[,|:]\s*L\d+\s*[,|:]\s*N\d+',v.strip())]
            if references:flag('internal_reference_in_cell',references)
            gaps=table.get('verification_gaps',[])
            if gaps:
                counts['unresolved_tables']+=1
                flag('unverified_rows',gaps)
                if table.get('semantic_review_completed'):flag('verification_state_conflict','Gaps present but marked completed')
            if rows and columns:
                repeated=[i for i,r in enumerate(rows) if r==columns]
                if repeated:flag('header_repeated_as_data',repeated)
                seen={};duplicates=[]
                for i,r in enumerate(rows):
                    if all(v in (None,'','—','-') for v in r):continue
                    identity=json.dumps(r,ensure_ascii=False,sort_keys=True)
                    if identity in seen:duplicates.append([seen[identity],i])
                    seen[identity]=i
                if duplicates:flag('identical_rows_review_required',duplicates)
            binding=table.get('source_binding')
            if binding and not binding.get('source_id'):flag('binding_without_source','Source-authored table has no source id')
    return {'status':state.get('run',{}).get('status'),'counts':counts,'findings':findings,
            'note':'Read-only structural diagnostics. Not a source accuracy, body quality, or end-to-end acceptance score.'}


if __name__=='__main__':
    folder=Path(__file__).resolve().parents[1]/'outputs/frozen_candidates'/sys.argv[1]
    result=audit(json.loads((folder/'state.json').read_text(encoding='utf-8-sig')))
    (folder/'structure-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ('status','counts','findings')},ensure_ascii=False,indent=2))
