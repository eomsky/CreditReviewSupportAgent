"""Export actual model outputs unchanged, with separate validation findings."""
from pathlib import Path
import json
import sys
import zipfile

BASE=Path(__file__).resolve().parents[1]
run=Path(sys.argv[1]).resolve()
data=json.loads((run/'result.json').read_text(encoding='utf-8'))
metrics={p.name.removesuffix('.metrics.json'):json.loads(p.read_text(encoding='utf-8')) for p in run.glob('*.metrics.json')}
findings=[]
for view,section in data['views'].items():
    for paragraph in section['paragraphs']:
        if any(fragment in paragraph['text'] for fragment in ['"}, {','"}],','"paragraphs"']):
            findings.append({'view':view,'paragraph_id':paragraph['id'],'type':'format','issue':'모델 본문 안에 JSON 구조 조각이 섞임. 원문 응답 보존; 자동 수정하지 않음.'})
manual=[
 {'view':'profitability','source':'35844.jpg · 1/7쪽 수익성 표','source_value':'2025년 영업이익률 19.61%','reported_value':'2025년(추정) 0.19%','issue':'비율과 기간 구분 오류'},
 {'view':'financial_stability','source':'35844.jpg · 1/7쪽 재무안정성 표','source_value':'2025년 유동비율 85.71%','reported_value':'25년 112.24%','issue':'다른 항목 또는 기간의 수치를 유동비율로 인용'},
 {'view':'financial_accounts','source':'35849.jpg · 6/7쪽 영업현황 본문','source_value':'전사 생산능력 50% 이상 증가 전망','reported_value':'생산능력 5배 확대','issue':'전망 규모 오독'}]
for issue in manual:
    body='\n'.join(p['text'] for p in data['views'][issue['view']]['paragraphs'])
    needles={'profitability':'0.19%','financial_stability':'112.24%','financial_accounts':'5배'}
    if needles[issue['view']] in body:findings.append({**issue,'type':'source_comparison'})
quality={'status':'failed' if findings else 'not_fully_reviewed','findings':findings,
 'scope':'대표 수치와 출력 형식만 대조함. 전체 금액 및 문장 검증 완료를 의미하지 않음.',
 'technical':{'actual_model_calls':len(metrics),'all_finished_stop':all(m['finish_reason']=='stop' for m in metrics.values()),'model':sorted(set(m['model'] for m in metrics.values())),'inference_seconds':round(sum(m['elapsed_seconds'] for m in metrics.values()),2)}}
data['report']['validation']=quality
data['audit']=[{'path':f.get('view',''),'reason':f['issue']+(' · 원문 '+f['source_value']+' / 모델 '+f['reported_value'] if 'source_value' in f else '')} for f in findings]
(run/'quality-review.json').write_text(json.dumps(quality,ensure_ascii=False,indent=2),encoding='utf-8')
(run/'reviewed-result.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
md=['# Colab 실제 생성 테스트 결과','\n실제 모델 응답 원문을 보존한 테스트 산출물이다. 내용 검수 미통과이며 업무용 확정 의견으로 사용할 수 없다.','\n모델: google/gemma-4-31B-it',f'\n실제 호출: {len(metrics)}회 / 추론 합계: {quality["technical"]["inference_seconds"]}초','\n입력: 첨부 JPG 6장의 Windows 한국어 OCR. Codex 작성 의견은 입력하지 않았다.','\n## 검수에서 발견한 문제']
md.extend('- '+f['issue']+(' (원문 '+f['source_value']+' / 모델 '+f['reported_value']+')' if 'source_value' in f else '') for f in findings)
for section in list(data['views'].values())+data['report']['sections']:
    md.append('\n## '+section['title'])
    for p in section['paragraphs']:md.extend(['\n**'+p.get('heading','')+'**\n',p['text']])
(run/'실제모델_생성결과_검수미통과.md').write_text('\n'.join(md),encoding='utf-8')
html=(BASE/'frontend'/'CreditReviewSupportAgent_UI_v0.1.66.html').read_text(encoding='utf-8')
payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
used=json.loads((run/'input.json').read_text(encoding='utf-8'))['payload']['generation_prompts']
prompt_payload=json.dumps({k:'\n\n'.join(p['text'] for p in value) for k,value in used.items()},ensure_ascii=False).replace('<','\\u003c')
loader='''(async()=>{
 await CreditReview.ready;
 const result=JSON.parse(document.getElementById('actual-result').textContent);
 result.id+='-actual-export';result.report.case_id=result.id;result.name+=' · 검수 미통과';
 const exists=CreditReview.snapshot().companies.some(c=>c.id===result.id);
 await CreditReview.loadCase(exists?{id:result.id}:result);
 if(!exists)await CreditReview.installPromptPack(JSON.parse(document.getElementById('actual-prompts').textContent));
 CreditReview.frame.navigate(0);
 const note=document.createElement('p');note.textContent='실제 Colab 모델 출력 · 수치/형식 검수 미통과';
 note.style.cssText='position:fixed;top:0;left:0;right:0;margin:0;padding:7px;background:#fff3db;color:#744600;text-align:center;font-size:12px;z-index:9999;pointer-events:none';document.body.append(note);
})();'''
html=html.replace('UI v0.1.66','실제 모델 결과 v0.1.71').replace('</body>','<script id="actual-result" type="application/json">'+payload+'</script><script id="actual-prompts" type="application/json">'+prompt_payload+'</script><script>'+loader+'</script></body>')
target=run/'CreditReviewSupportAgent_실제모델결과_v0.1.71.html'
target.write_text(html,encoding='utf-8')
downloads=Path('C:/Users/lasts/Downloads')
for p in [target,run/'실제모델_생성결과_검수미통과.md']:(downloads/p.name).write_bytes(p.read_bytes())
with zipfile.ZipFile(downloads/'CreditReviewSupportAgent_실제테스트_v0.1.71.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in run.iterdir():
        if p.is_file():z.write(p,p.name)
print(json.dumps(quality['technical'],ensure_ascii=False))
print('Quality status:',quality['status'],'findings:',len(findings))
