"""Export comparable source artifacts; counts are descriptive, not quality scores."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
KEYS=['financial_accounts','profitability','financial_stability','cashflow_repayment','customer_concentration','summary_2']

def load(path):return json.loads(path.read_text(encoding='utf-8'))

def text(section):return '\n\n'.join(p.get('text','') for p in section.get('paragraphs',[]))

def tables(section):
    result=[]
    for t in section.get('tables',[]):
        result.append(t.get('caption','표'))
        rows=[t.get('columns',[])]+t.get('rows',[])
        result.append('```text\n'+'\n'.join(' | '.join('—' if x is None else str(x) for x in row) for row in rows)+'\n```')
    return '\n\n'.join(result)

def compare(candidate):
    folder=ROOT/'outputs/frozen_candidates'/candidate
    state=load(folder/'state.json')
    baseline=ROOT/'outputs/experiments/20260914/frozen/baseline_run'
    rows=[];details=[]
    for key in KEYS:
        old=load(baseline/(key+'.refinement.result.json'))
        new=state.get('views',{}).get(key,{})
        title=new.get('title') or old.get('title') or key
        reviewed=bool(new.get('refinement'))
        rows.append(f"| {title} | {len(text(old)):,} | {len(text(new)):,} | {'검토 결과 있음' if reviewed else '검토 미완료'} |")
        details.append(f'## {title}\n\n### 프리징본\n\n{text(old)}\n\n{tables(old)}\n\n### {candidate}\n\n{text(new)}\n\n{tables(new)}')
    report=state.get('report',{}).get('sections',[])
    header=f'''# {candidate}와 프리징본 — 원문 비교용 출력

후보 실행 상태: {state.get('run',{}).get('status','미확인')}. 아래 길이와 검토 메타데이터는 품질 점수가 아니다. 숫자·기준·논리·근거를 직접 비교해야 한다.

동결 기준 실행은 전체 심사보고서 완료본이 아니므로, 보고서 전체 품질을 동일 완료본과 비교했다고 주장할 수 없다. 아래는 동결된 6개 의견의 최종 검토 결과와 후보의 현재 저장 결과다.

| 항목 | 프리징 본문 글자 수 | 후보 본문 글자 수 | 후보 상태 |
|---|---:|---:|---|
'''
    content=header+'\n'.join(rows)+'\n\n'+'\n\n'.join(details)
    if report:
        content+='\n\n## 후보 심사보고서 — 별도 원문 검증 대상\n\n'
        content+='\n\n'.join(f"### {s.get('title','')}\n\n{text(s)}\n\n{tables(s)}" for s in report)
    (folder/'comparison.md').write_text(content,encoding='utf-8')
    return folder/'comparison.md'

if __name__=='__main__':print(compare(sys.argv[1]))
