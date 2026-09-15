"""Record the manually reviewed cold trial; preserve exact accepted artifacts."""
import json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=root/'outputs/step_trials/C20.8s-cold-r1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
result=read(folder/'step-result.json');audit=read(folder/'materialization-audit.json')
if result['status']!='completed' or result['elapsed_seconds']>90 or audit['fixed_cells_verified']!=40:raise ValueError('Acceptance prerequisites failed')
review='''C20.8s-cold-r1 가 초안 검토: 품질 통과.
새 원문DB·82개 정규화후보에서 통합검수와 해석을 다시 실행한 결과이다.
고정표 40셀 일치, 손익/법인세/자본/단기상환/전망 설명 유지, 자산 문단 S1 한정 및 상세표 혼재 제거를 full-output.txt와 원문SQL에 대조했다.
현재 index.html의 렌더러를 분리된 브라우저 저장공간에서 사용하여 5열·10행 고정표, 단일 헤더, 감가상각비 줄바꿈 및 본문 표시를 화면 확인했다.
연속 측정76.237초: 목표70초+20초 이내 임시 시간 통과. 원본 파일 추출 및 벡터 인덱스 구축은 미포함. 전체 보고서 성과가 아니다.
이 결과를 보존하여 다음 가 검토 단계에 사용한다. 전체20분/다른회사/다른형식 품질 검증은 남아 있다.
'''
(folder/'quality-review.md').write_text(review,encoding='utf-8')
result.update(quality_status='pass',allow_step2=True,quality_pass_version='C20.8s',time_pass_version='C20.8s',quality_evidence='quality-review.md')
result['artifact_sha256']={name:hashlib.sha256((folder/name).read_bytes()).hexdigest() for name in ('materialized-artifact.json','numeric.sqlite','full-output.txt','quality-review.md')}
(folder/'step-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
path=root/'outputs/business_report_test/experiment-structuring-steps.json';monitor=read(path)
monitor['steps']['1'].update(status='completed',elapsed_seconds=result['elapsed_seconds'],quality_status='pass',time_status='provisional_pass',pass_version='C20.8s',quality_pass_version='C20.8s',time_pass_version='C20.8s',active=False,quality_reason='76.24초 통과(임시), 새 응답 품질·고정표 화면 확인. 추출 원문부터 가 초안까지; 파일 파싱/벡터 구축 제외.')
monitor['steps']['2']={'status':'pending','elapsed_seconds':None,'quality_status':'unassessed','active':True,'quality_reason':'가 검토 단계 준비. 기존 및 정형 DB 통과 초안 재사용.'}
path.write_text(json.dumps(monitor,ensure_ascii=False,indent=2),encoding='utf-8')
print({'quality':'pass','time':result['time_status'],'seconds':result['elapsed_seconds']})
