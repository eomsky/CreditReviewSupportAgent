"""Preserve C20.6s evidence and test interpretation scope safeguards separately."""
import json,sqlite3,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
old=root/'outputs/step_trials/C20.6s';out=root/'outputs/step_trials/C20.7s'
out.mkdir(exist_ok=False)
c=sqlite3.connect(old/'numeric.sqlite');c.row_factory=sqlite3.Row
building=[dict(r) for r in c.execute('SELECT account,period,value_decimal,source_id FROM approved_facts WHERE account=?',('건물',))]
c.close()
(old/'semantic-review.json').write_text(json.dumps({'quality_status':'fail','allow_next_step':False,'reason':'고정 요약표 유형자산 증가를 설명하며 기준 미확정 상세표 건물 값을 특히라는 표현으로 연결. 수치 자체는 맞지만 표 간 구성관계는 입증되지 않음.','building_source_values':building,'correct_parts':['손익 세전·법인세·순손실 연결','차입금·단기부채 증감','전망 수치','고정표 40셀 SQL 대조'],'end_to_end':False},ensure_ascii=False,indent=2),encoding='utf-8')
for name in ('numeric.sqlite','metadata-candidates.json','joint-validation.json','sql-query-audit.json'):
    shutil.copy2(old/name,out/name)
request=json.loads((old/'interpretation.request.json').read_text())
request['messages'][0]['content']+='\n표 간 기준 검증: basis가 unknown인 서로 다른 표의 수치를 하나의 총액과 구성항목, 증감 원인, 같은 기준의 비교로 연결하지 않는다. 특히/그중/주로 등의 표현도 구성관계를 주장하므로 같은 표 또는 명시적 기준 일치 근거가 있어야 한다. 다른 표만 제공하는 보조 계정은 해당 상세표의 독립 관찰로 서술하고 고정 요약표의 구성요인으로 단정하지 않는다. 같은 기간이라는 사실만으로 기준 일치가 입증되지 않는다. 모든 필수 논점과 법인세 설명은 유지한다.'
(out/'interpretation.request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),encoding='utf-8')
(out/'reuse-manifest.json').write_text(json.dumps({'version':'C20.7s','parent':'C20.6s','change':'미확정 표 간 구성관계 추론 금지, 보조 계정 독립 관찰','reused_normalization_seconds':25.062,'scope':'interpretation_only_candidate','cold_full_step_measured':False},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(building,ensure_ascii=False))
