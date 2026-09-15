"""Retry only the actual failed report with a stricter nonempty text schema."""
from pathlib import Path
import json
import sys
import time
import hashlib
from live_html_test import remote, REPORT, VIEWS, blocks, dump, CASE, config

run=Path(sys.argv[1]).resolve()
payload=json.loads((run/'report.request.json').read_text(encoding='utf-8'))
payload['structured_outputs']={'json':REPORT}
dump(run/'report_retry.request.json',payload)
start=time.monotonic()
answer=remote('/chat/completions',payload,timeout=360)
dump(run/'report_retry.response.json',answer)
choice=answer['choices'][0]
if choice.get('finish_reason')!='stop':raise ValueError('Report did not finish normally')
report=json.loads(choice['message']['content'])
if len(report['sections'])!=7:raise ValueError('Missing sections')
for i,s in enumerate(report['sections']):blocks(s,run.name+'-report-'+str(i))
dump(run/'report_retry.metrics.json',{'response_id':answer.get('id'),'model':answer.get('model'),'elapsed_seconds':round(time.monotonic()-start,2),'usage':answer.get('usage'),'finish_reason':choice.get('finish_reason'),'request_sha256':hashlib.sha256(json.dumps(payload,ensure_ascii=False).encode()).hexdigest()})
views={}
for key in VIEWS:
    raw=json.loads((run/(key+'.response.json')).read_text(encoding='utf-8'))
    views[key]=blocks(json.loads(raw['choices'][0]['message']['content']),run.name+'-'+key)
report.update(case_id=CASE,draft=True,provenance={'method':'Colab actual model completions; report schema retry','model':config()['model'],'run_id':run.name,'source':'Windows OCR ko; uncorrected'})
result={'id':CASE,'name':'에스케이실트론(주) · Colab 실제 생성 테스트','revision':1,'report':report,'views':views,'run':{'id':run.name,'status':'completed','stage':'완료 (보고서 재호출)','completed_calls':7,'actual_attempts':8}}
dump(run/'result.json',result)
print('Actual report retry completed; result saved.',flush=True)
