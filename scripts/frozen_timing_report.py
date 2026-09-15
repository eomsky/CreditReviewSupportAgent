"""Summarize recorded calls without counting overlapping calls as wall time."""
import json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LABELS={'financial_accounts':'가','profitability':'나','financial_stability':'다','customer_concentration':'마','summary_2':'종합의견2'}
def classify(req):
    keys=set(req.get('structured_outputs',{}).get('json',{}).get('properties',{}))
    if keys & {'facts','numeric_evidence','calculations','key_relationships','required_tables','additional_tables','search_queries','source_excerpts','conflicts'}:return '자료 검토'
    if keys & {'revisions','quality_checks','additions','remaining_gaps','information_guidance','table_cell_reviews'}:return '본문·표 검토'
    if keys and all(k.startswith('T') for k in keys):return '표 검토'
    return '생성'

def summarize(folder):
    calls=json.loads((folder/'calls.json').read_text(encoding='utf-8'))
    rows=[]
    for c in calls:
        req=json.loads((folder/'calls'/f"{c['number']:03}.request.json").read_text(encoding='utf-8'))
        rows.append({**c,'operation':classify(req)})
    groups={}
    for c in rows:
        key=c['stage'].split(':')[0]
        g=groups.setdefault(key,{'start':c['started_seconds'],'end':0,'call_seconds':0,'output_tokens':0,'calls':0})
        g['start']=min(g['start'],c['started_seconds'])
        g['end']=max(g['end'],c['started_seconds']+c.get('elapsed_seconds',0))
        g['call_seconds']+=c.get('elapsed_seconds',0)
        g['output_tokens']+=(c.get('usage') or {}).get('completion_tokens',0)
        g['calls']+=1
    for g in groups.values():g['wall_span_seconds']=round(g['end']-g['start'],2)
    terminal=json.loads((folder/'results.json').read_text(encoding='utf-8')) if (folder/'results.json').exists() else {}
    interruption=json.loads((folder/'interruption.json').read_text(encoding='utf-8')) if (folder/'interruption.json').exists() else None
    result={'calls':rows,'phase_spans':groups,'terminal_status':terminal.get('status','running'),
            'elapsed_seconds':terminal.get('elapsed_seconds'),
            'completed_end_to_end':terminal.get('status')=='completed',
            'successful_duration_seconds':terminal.get('elapsed_seconds') if terminal.get('status')=='completed' and not interruption else None,
            'interruption':interruption,'quality_status':'requires_source_and_body_review',
            'note':'Call durations overlap. Only completed end-to-end runs without an infrastructure interruption contribute to successful-duration comparisons. Completion is not quality acceptance.'}
    (folder/'timing-analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result

if __name__=='__main__':
    r=summarize(ROOT/'outputs/frozen_candidates'/sys.argv[1])
    print(json.dumps(r['phase_spans'],ensure_ascii=False,indent=2))
