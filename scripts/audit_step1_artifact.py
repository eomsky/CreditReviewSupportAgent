"""Mechanical step-1 checks. Body/source judgement is deliberately separate."""
import json,sys
from pathlib import Path
from frozen_exact_template_source import bind_templates

root=Path(__file__).resolve().parents[1]
folder=root/'outputs/frozen_candidates'/sys.argv[1]
sys.path.insert(0,str(folder/'code/scripts'))
import fixed_review_tables
from review_documents import PRIORITIES
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
state=read(folder/'state.json');result=read(folder/'results.json')
draft=state['views']['financial_accounts']
sources=read(folder/'run/financial_accounts.evidence.json')
bound=bind_templates(sources,fixed_review_tables.TEMPLATES['financial_accounts'],PRIORITIES)
checks={'step1_only':list(state['views'])==['financial_accounts'] and not state['report'].get('sections'),
        'no_other_step_calls':all(c['stage']=='draft:financial_accounts' for c in read(folder/'calls.json')),
        'completed':result['status']=='completed','time_pass':result['elapsed_seconds']<=70}
table_checks=[]
for table in draft.get('tables',[]):
    matches=[b for b in bound.values() if b['source_id']==table.get('source_binding',{}).get('source_id')]
    matched=len(matches)==1 and all(row[1:]==matches[0].get(f'r{i}') for i,row in enumerate(table['rows']))
    table_checks.append(matched)
checks['fixed_source_values_preserved']=bool(table_checks) and all(table_checks)
ids={s['id'] for s in sources}
checks['paragraph_citations_resolve']=all(p.get('sources') and all(s['id'] in ids for s in p['sources']) for p in draft['paragraphs'])
audit={'end_to_end':False,'elapsed_seconds':result['elapsed_seconds'],'checks':checks,
       'time_status':('pass' if result['elapsed_seconds']<=70 and result['status']=='completed' else 'provisional_pass' if result['elapsed_seconds']<=110 and result['status']=='completed' else 'fail'),
       'quality_status':'requires_body_source_comparison','allow_step2':False}
(folder/'step1-mechanical-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False))
