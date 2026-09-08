# 여신 심사지원 에이전트 인수인계

작성일: 2026-09-09  
저장소: https://github.com/eomsky/CreditReviewSupportAgent  
작업 브랜치: `codex/credit-review-harness`

## 현재 목표

첨부된 실제 여신심사보고서와 같은 목차, 표 구성, 정보 밀도, 심사자 문체를 재현하는 것이 목표임. 문장은 `~함`, `~판단됨`, `~필요함` 형태로 작성하며, 근거가 없는 수치나 결론을 만들지 않음.

## 현재 처리 구조

보고서 본문은 목차 단위로 한 번씩 생성함. 재추론은 사용하지 않으며 총 호출 구조는 아래와 같음.

1. 업체현황
2. 여신 개요 및 신청 사유
3. 사업 분석
4. 주요 리스크 분석
5. 재무 분석 — 성장·수익·안정성
6. 재무 분석 — 현금·자산·전망
7. 상환재원
8. 특이사항
9. 전체 보고서의 전문 표 생성 및 소제목별 배치
10. 금액 단위·자릿수 감사 목록 생성

재무 분석은 토큰 초과를 줄이기 위해 2회로 분리됨. 목차 호출은 의존관계를 지키면서 가능한 항목을 병렬 처리함. 각 호출의 실제 시작·종료·소요시간은 실행 폴더의 `section_timings.json`에 저장되고 앱의 `파트별 소요시간`에서 확인할 수 있음.

## 금액 감사 정책

금액 감사 LLM은 보고서를 직접 수정하지 않음. 잘못된 금액이 있으면 JSON의 `findings` 목록에 위치, 현재값, 권고값, 발생 순서, 오류 종류, 사유만 저장함. 앱의 `금액 검수 결과 (N건) — 보고서 미반영`에서 목록을 확인할 수 있음. 보고서 본문과 생성 표는 감사 결과와 관계없이 생성된 상태 그대로 유지됨.

원화 표기 기준은 10억원 이하일 때 백만원, 10억원 초과일 때 억원이며 소수점은 사용하지 않음. 외화는 원 통화와 단위를 유지함. 금액이 아닌 날짜, 비율, 금리, 주식수, 생산량은 변경 대상으로 취급하지 않음.

## 표 생성 정책

표 생성 LLM은 본문을 다시 쓰지 않고 표만 생성함. 업체현황, 여신조건, 제품·생산, 리스크, 3~5개년 재무, 상환재원, 신용등급·Exposure·우발채무 중 자료 근거가 있는 표만 최대 10개 생성함. 표는 관련 소제목 바로 뒤에 배치됨. 각 행은 보고서 내 근거 경로를 가져야 하며, 근거와 일치하지 않는 숫자는 로컬 검증에서 제외됨.

## 여러 파일 업로드

앱의 `자료 업로드 (여러 파일 선택 가능)`에서 PDF와 JSON을 2개 이상 동시에 선택할 수 있음. 선택한 모든 파일은 한 심사건으로 합쳐 분석하며 문서 해시로 중복을 제거함. 파일당 제한은 200MB임.

## 현재 실행 결과

Codespace 실행 폴더:

`/workspaces/CreditReviewSupportAgent/workspace/cases/SKSiltron_FinalHybrid_20260908/runs/run_d3575d26b7fc48d38364599b8f93c297`

본문 8개 목차와 표 생성은 완료되어 보존되어 있음. 이전 금액 검수 응답은 2,500 출력 토큰 한도에 도달해 중단되었으며 보고서에는 적용되지 않았음. 현재 코드는 금액 감사 출력 한도를 6,000으로 확대하고, 현재값과 권고값이 같은 항목은 반환하지 않도록 강화함. LLM 서버를 다시 실행한 뒤 앱에서 `보고서 작성 계속`을 누르면 본문과 표를 재생성하지 않고 마지막 금액 감사만 재개함.

## Codespace와 앱

Codespace:

`https://cautious-halibut-qv957wg9pvq92vq9.github.dev/`

앱:

`https://cautious-halibut-qv957wg9pvq92vq9-8501.app.github.dev/`

앱 실행 명령:

```bash
cd /workspaces/CreditReviewSupportAgent
python -m streamlit run app/workbench.py --server.port 8501 --server.address 0.0.0.0
```

포트 8501의 공개 범위를 Public으로 설정해야 외부 앱 주소에서 접속할 수 있음.

## Gemma 4 31B 서버

Colab 노트북:

`https://colab.research.google.com/drive/1sYZxQlFkE6F_wDIvnPbeRAKHPpOEUA5h`

현재 Colab 런타임은 사용자의 요청에 따라 종료된 상태임. 다시 사용할 때 A100 80GB 런타임에서 환경 준비 셀과 BF16 32K 서버 셀을 실행함. 서버가 출력한 연결 정보를 Codespace의 `workspace/llm_connection.json`에 저장함. 이 파일에는 API 키가 있으므로 Git과 공유 스냅샷에 포함하면 안 됨.

연결 확인:

```bash
python -c "from credit_review.llm import ColabClient; c=ColabClient(); c.check(); print(c.model, c.context_tokens)"
```

## 검증

Codespace의 최신 전체 테스트 기준은 139개 통과임. 변경 후 기본 검증 명령은 아래와 같음.

```bash
python -m pytest -q --basetemp=/tmp/credit-review-pytest
```

로컬 Windows 환경에서는 설치된 scikit-learn 버전 차이로 일부 환경 검증이 실패할 수 있으므로, 최종 판정은 저장소의 의존성이 설치된 Codespace 결과를 사용함.

## 주요 파일

- `app/workbench.py`: 업로드, 실행, 진행상태, 결과 화면
- `src/credit_review/prepared.py`: 8개 목차 호출 순서와 병렬 처리
- `src/credit_review/section_prompts.py`: 목차별 상세 작성 지침
- `src/credit_review/table_generation.py`: 표 근거 검증과 배치
- `src/credit_review/monetary_review.py`: 읽기 전용 금액 감사 목록
- `src/credit_review/reporting.py`: 보고서와 표 렌더링
- `tests/test_monetary_review.py`: 금액 감사가 본문을 수정하지 않는지 검증
- `tests/test_table_generation.py`: 표 배치와 수치 근거 검증

## 보안 및 운영 주의

`workspace/llm_connection.json`, Colab API 키, 터널 주소는 커밋하거나 공유 압축파일에 넣지 않음. Google Drive에는 `git archive`로 만든 추적 파일 스냅샷과 이 인수인계 파일만 적재함.
