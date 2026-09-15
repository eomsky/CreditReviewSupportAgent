"""Preview a saved trial using the current UI renderer and isolated browser storage."""
import json,argparse,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('folder');p.add_argument('--key',default='financial_accounts',choices=['financial_accounts','profitability','financial_stability','cashflow_repayment','customer_concentration','summary_2','report']);a=p.parse_args();folder=Path(a.folder)
root=Path(__file__).resolve().parents[1];web=root/'outputs/business_report_test'
artifact_path=folder/'integrated-output.json'
if not artifact_path.exists():artifact_path=folder/'materialized-artifact.json'
if not artifact_path.exists():artifact_path=folder/'reviewed-artifact.json'
data=json.loads(artifact_path.read_text(encoding='utf-8'))
integrated=data if 'report' in data and 'views' in data else None
if integrated:data=integrated['report'] if a.key=='report' else integrated['views'][a.key]
paragraphs=data.get('paragraphs',[]) if a.key!='report' else [p for section in data['sections'] for p in section['paragraphs']]
for i,paragraph in enumerate(paragraphs):
    if 'source_ids' not in paragraph:continue
    paragraph['id']='structured-'+str(i)
    paragraph['sources']=[{'id':sid,'label':sid,'text':next(s['text'] for s in data['sources'] if s['id']==sid)} for sid in paragraph['source_ids']]
payload={'name':'정형 DB 초안 · '+folder.name,'report':data if a.key=='report' else {'sections':[]},'views':{} if a.key=='report' else {a.key:data}}
if integrated:payload.update(report=integrated['report'],views=integrated['views'])
encoded=json.dumps(payload,ensure_ascii=False).replace('</','<\\/')
source=(web/'index.html').read_text(encoding='utf-8')
source=source.replace("indexedDB.open('credit-review-ui-0166',1)","indexedDB.open('credit-review-structuring-preview',1)")
script="<script>(async()=>{await CreditReview.ready;const state="+encoded+";CreditReview.loadReport({...state.report,case_id:CreditReview.snapshot().active_case_id},state.views);document.getElementById('reviewHome').hidden=true;if(document.getElementById('companyName'))document.getElementById('companyName').textContent=state.name;CreditReview.frame.navigate("+str({'financial_accounts':1,'profitability':2,'financial_stability':3,'cashflow_repayment':4,'customer_concentration':5,'summary_2':6,'report':7}[a.key])+");})();</script>"
(web/'structuring-preview.html').write_text(source+script,encoding='utf-8')
(folder/'preview-manifest.json').write_text(json.dumps({'renderer_sha256':hashlib.sha256((web/'index.html').read_bytes()).hexdigest(),'isolated_storage':True,'preview':'structuring-preview.html'},indent=2),encoding='utf-8')
