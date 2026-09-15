"""Derive an asset paragraph's allowed table from the fixed table provenance."""
import json,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1];old=root/'outputs/step_trials/C20.7s';out=root/'outputs/step_trials/C20.8s';out.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
request=read(old/'interpretation.request.json');user=json.loads(request['messages'][1]['content'])
reference=read(root/'outputs/frozen_candidates/C20.4-step1-r1/state.json')['views']['financial_accounts']['tables']
bound={t['source_binding']['source_id'] for t in reference}
audit=read(old/'sql-query-audit.json')
table_ids={q['table_id'] for q in audit['queries'] if q['rows'] and {r['source_id'] for r in q['rows']}<=bound}
allowed=[s['id'] for s in user['sources'] if json.loads(s['text'])['table_id'] in table_ids]
if not allowed:raise ValueError('No fixed table provenance match')
node=request['structured_outputs']['json']['properties']['analysis_paragraphs']['properties']['assets_and_financing']
node['properties']['source_ids']['items']['enum']=allowed
node['properties']={'table_scope':{'type':'string','enum':allowed},**node['properties']}
node['required']=['table_scope',*node['required']]
request['messages'][0]['content']+='\nassets_and_financing 문단은 table_scope에 선택한 고정표 출처 안의 계정과 수치 및 그 표 내부의 증감만 해석한다. 다른 표의 계정이나 숫자를 이 문단에 추가하지 않는다. 이는 총액과 상세항목의 미확정 관계를 단정하지 않기 위한 출처 경계다. 나머지 논점은 제공된 관련 표를 독립 근거로 사용한다.'
for name in ('numeric.sqlite','metadata-candidates.json','joint-validation.json','sql-query-audit.json'):shutil.copy2(old/name,out/name)
(out/'interpretation.request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'reuse-manifest.json').write_text(json.dumps({'version':'C20.8s','parent':'C20.7s','asset_allowed_source_ids':allowed,'change':'고정표 원문 연결에서 자산문단 출처 enum 도출','reused_normalization_seconds':25.062,'cold_full_step_measured':False},ensure_ascii=False,indent=2),encoding='utf-8')
print({'allowed':allowed})
