"""Summarize controlled experiments without calling partial runs completed tests."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    if not path.exists():return None
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    rows=[];details={}
    for candidate in ['C1','C2','C4']:
        folder=ROOT/'outputs/frozen_candidates'/candidate
        result=read(folder/'results.json')
        state=read(folder/'state.json')
        calls=read(folder/'calls.json') or []
        quality=read(folder/'quality-evaluation.json') or {}
        quality_label=quality.get('label','미평가')
        status=result['status'] if result else ('실행 중 또는 상태 확인 필요' if folder.exists() else '대기')
        elapsed=result.get('elapsed_seconds') if result else None
        groups={}
        for c in calls:
            if c.get('status')!='completed':continue
            op=c.get('operation','unknown')
            group=groups.setdefault(op,{'calls':0,'call_seconds':0,'output_tokens':0})
            group['calls']+=1;group['call_seconds']+=c.get('elapsed_seconds',0)
            group['output_tokens']+=(c.get('usage') or {}).get('completion_tokens',0)
        details[candidate]={'status':status,'terminal_elapsed_seconds':elapsed,
            'completed_steps':(state or {}).get('run',{}).get('completed_calls'),
            'total_steps':(state or {}).get('run',{}).get('total_calls'),
            'operations':groups,'quality':quality or '미평가 — 원문과 최종 검토 결과 대조 필요'}
        rows.append(f"| {candidate} | {status} | {round(elapsed,2) if elapsed else '—'} | {quality_label} |")
    text='# 1·2·4안 비교 — 중간 기록\n\n3안은 사용자 요청으로 중단하고 참고 기록으로만 보존했다. 전체 완료와 최종 품질 확인 전이다. 실패·중단 시간은 성공 전체 소요시간이 아니다.\n\n| 안 | 상태 | 종료 시 경과 초 | 최종 품질 |\n|---|---|---:|---|\n'+'\n'.join(rows)
    text+='\n\n세부 호출 합계는 전체 경과시간과 다르며 미완료 호출은 제외했다. C1 연결 오류는 추출기/검색 성능 결과와 구분한다.\n'
    out=ROOT/'outputs/frozen_candidates/controlled-comparison'
    (out/'COMPARISON.md').write_text(text,encoding='utf-8')
    (out/'comparison-summary.json').write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding='utf-8')
    print(text)


if __name__=='__main__':main()
