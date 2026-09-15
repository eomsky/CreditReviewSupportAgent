"""Create a separate integrated candidate, preserving accepted trial artifacts."""
import copy, hashlib, json, time
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]; base=root/'outputs/step_trials'
    out=base/'C20.36-step19-integration';out.mkdir(exist_ok=False);start=time.perf_counter()
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
    parent=base/'C20.35-step18-review';gate=read(parent/'step-result.json');assert gate['allow_step19']
    for n,h in gate['artifact_sha256'].items():assert hashlib.sha256((parent/n).read_bytes()).hexdigest()==h
    report=read(parent/'reviewed-artifact.json')
    paragraphs={p['id']:p for s in report['sections'] for p in s['paragraphs']}
    runs={'financial_accounts':'C20.13.1s-step2-replay','profitability':'C20.18.1s-step4-r1','financial_stability':'C20.24s-step6-r1','cashflow_repayment':'C20.25.2s-step8-replay','customer_concentration':'C20.27.1.1s-step10-replay','summary_2':'C20.29.1-step12-r1'}
    views={};lineage=[];changes=[]
    for key,run in runs.items():
        f=base/run;g=read(f/'step-result.json');assert g['quality_status']=='pass'
        for n,h in g.get('artifact_sha256',{}).items():assert hashlib.sha256((f/n).read_bytes()).hexdigest()==h
        views[key]=read(f/'reviewed-artifact.json')
        lineage.append({'view':key,'path':str(f),'artifact_sha256':hashlib.sha256((f/'reviewed-artifact.json').read_bytes()).hexdigest()})
    before=copy.deepcopy(views)
    # Explicit integration contracts refer to stable paragraph identities, never row positions.
    contracts=[('summary_2','section-p8','report-part1-s1-p5',''),
               ('summary_2','section-p12','report-part3-s3-p2',' 행정 제재 및 입찰 제한 내역은 현재 확보된 발췌 자료에서 확인되지 않음.'),
               ('summary_2','section-p13','report-part3-s2-p2',' 2025년 말 기준 총차입금은 1.56조 원으로 증가하여 금융비용 부담도 검토할 필요가 있음.'),
               ('summary_2','section-p17','report-part3-s1-p4','')]
    for view,pid,rid,suffix in contracts:
        p=next(p for p in views[view]['paragraphs'] if p['id']==pid);source=paragraphs[rid]
        old=copy.deepcopy(p);p['text']=source['text']+suffix
        # Retain original evidence for the supplementary fact as well as new evidence.
        combined=copy.deepcopy(source['sources'])+(old.get('sources',[]) if suffix else [])
        unique={}
        for s in combined:unique.setdefault((s.get('document_id'),s.get('page'),s['text']),s)
        p['sources']=list(unique.values());p.pop('source_ids',None)
        changes.append({'view':view,'paragraph_id':pid,'approved_report_paragraph':rid,'before':old['text'],'after':p['text']})
    old_forecast=next(p['text'] for p in before['summary_2']['paragraphs'] if p['id']=='section-p17')
    for key in ['cashflow_repayment','financial_stability']:
        for p in views[key]['paragraphs']:
            # Only exact matching accepted sentences are synchronized; no broad substitution.
            if p['text']==old_forecast:
                source=paragraphs['report-part3-s1-p4'];changes.append({'view':key,'paragraph_id':p['id'],'before':p['text'],'after':source['text']})
                p['text']=source['text'];p['sources']=copy.deepcopy(source['sources']);p.pop('source_ids',None)
    for key in views:assert views[key]['tables']==before[key]['tables']
    payload={'report':report,'views':views,'candidate':'C20.36'}
    save(out/'integrated-output.json',payload);save(out/'reviewed-artifact.json',report)
    save(out/'integration-changes.json',changes);save(out/'lineage.json',lineage)
    save(out/'integration-audit.json',{'elapsed_seconds':time.perf_counter()-start,'all_six_view_tables_unchanged':True,'report_unchanged_from_step18':True,'changed_view_paragraphs':len(changes),'end_to_end':False,'quality_status':'pending_visual_and_whole_output_review'})
    print(json.dumps(read(out/'integration-audit.json')))

if __name__=='__main__':main()
