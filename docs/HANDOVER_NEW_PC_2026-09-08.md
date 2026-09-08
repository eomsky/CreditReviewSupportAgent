# 여신 심사지원 에이전트 — 다른 PC 인수인계

작성일: 2026-09-08 (KST). 마지막 실행 검증 시점: 2026-09-08 06:49:39 KST.
이 문서는 다른 PC에서 작업을 이어가기 위한 상태 기록이다. 서버의 현재 생존 여부는 새 PC에서 확인해야 한다. 이번 인수인계 반영은 문서 추가이며 애플리케이션 코드 변경·학습·서버 재시작은 하지 않았다.

> **2026-09-08 후속 변경:** 아래 야간 측정 기록 이후 보고서 생성 구조를 바꿨다. 현재 기본 LIVE 경로는 기준 보고서의 7개 목차를 처음부터 끝까지 순차 순회하며, **목차 하나당 LLM 1회, 총 7회**만 호출한다. 재무 기초 추론, 후속 근거 요청, 품질 재추론, 요인별 재작성, 별도 최종 종합 호출은 제거했다. 목차 호출 직전에 시도 마커를 저장하므로 재개해도 완료·실패 목차를 다시 호출하지 않는다. 상세 규격은 [기준 심사보고서 구성과 단방향 생성 계약](REFERENCE_REPORT_BLUEPRINT.md)을 따른다. 이 변경의 로컬 회귀 테스트는 `.venv_spt`에서 127개 모두 통과했다. 아래의 9회 호출·120초 측정값은 변경 전 역사적 결과이며 현재 호출 구조 설명으로 사용하지 않는다.

## 1. 가장 먼저 알아야 할 상태

- 01:49:39~06:49:39의 5시간 야간 최적화·SFT 작업은 종료했다. 추가 실험 없음. 자동 후속 작업 `5-lora`는 종료 기록상 PAUSED다. 과거 시간 제한 작업을 자동 재개하지 않는다.
- **예시 보고서 수준의 심사 품질과 신규 PDF 기준 안정적인 120초 이내 완료를 함께 달성하지 못했다.** 보고서는 검토용 초안이다.
- 정상 UI 실행에서 준비된 자료 기준 내부 85.58초, 30개 판단, LLM 9회, 최초 보고서 지표 13.59초를 기록했다. 업로드·최초 PDF 인식을 포함한 전체 지연 보장이 아니다.
- 기본 모델은 `google/gemma-4-26B-A4B-it`. LoRA는 학습·보관했지만 기본값으로 승격하지 않았으며 기본 가중치와 병합하지 않았다.
- 기존 프리징 Drive 운영 자산 및 기존 HTML은 수정하지 않았다. 개발은 별도 하네스에서 진행했다.
- 마지막 회귀 테스트 128개 통과. 이는 의미적 심사 품질 인증이 아니다. 인수인계 작성 시 로컬 저장소 변경 사항은 없었고 HEAD는 아래와 같았다.

## 2. 코드와 작업 환경

- 저장소: https://github.com/eomsky/CreditReviewSupportAgent
- 개발 브랜치: `codex/credit-review-harness`
- 최종 커밋: `d98d7675e6047e370fb75908b0aa2f05cab4bca2`
- 변경하지 않는 비교 기준 `v1`: `54ffbad83ae821d72cf5c697e15f235ccb49090d`
- 코드·공개 문서: GitHub. 실제 기업 자료·보고서·학습 데이터·가중치·복구 기록: 비공개 Drive. 작업 사본·캐시: Codespaces.
- 명령은 실제 CreditReviewSupportAgent 저장소 루트에서 실행한다.
- 구성: Codespaces가 PDF 처리·검색·자료 구조화·Python 계산·보고서 UI를 담당하고 Colab은 LLM 추론 서버를 담당한다. 실제 확인한 GPU는 A100 80GB다.

### 새 PC에서 시작

1. 같은 GitHub·Google 계정으로 로그인하고 기존 Codespace 및 Colab 런타임이 살아 있는지 확인한다. 살아 있다면 기존 환경을 우선 사용한다. 기존 경로·포트·프로세스 ID는 재사용 전 확인한다.
2. 기존 Codespace에서는 `git status --short`와 `git rev-parse HEAD`로 변경 사항과 버전을 확인한다. 새 체크아웃이 필요하면 아래 명령을 사용한다.

```bash
git clone --branch codex/credit-review-harness https://github.com/eomsky/CreditReviewSupportAgent.git
cd CreditReviewSupportAgent
git rev-parse HEAD
```

위 최종 커밋 이후 변경이 있다면 이 문서와 차이를 먼저 확인한다. 기존 변경을 강제로 덮어쓰지 않는다. 새 Codespaces/Linux 환경의 설치·실행 명령은 다음과 같다. 다른 PC에 대형 모델을 직접 설치할 필요는 없다.

```bash
pip install -e '.[test]'
docker build -f docker/calculator.Dockerfile -t credit-review-calculator:0.1 .
python -m streamlit run app/workbench.py --server.address 0.0.0.0
```

Codespaces Ports의 8501을 브라우저로 연다. Private 포트를 유지한다. 기존 앱 서버가 살아 있다면 중복으로 띄우지 않는다. Python 계산은 Docker가 필요하다.

## 3. LLM 연결 복구

- 기본 모델 revision: `4d7ae4984b7db7de8f8457170b3f1a419ee76d52`.
- 새 Colab 복구 노트북: 비공개 인수인계 묶음의 한국어 복구 안내에서 링크 확인
- 노트북은 실행 출력·비밀값 없는 3개 셀이며 revision 고정 및 컴파일 검증을 마쳤다. 완전히 새로운 Colab 런타임에서 설치부터 끝까지 재검증한 것은 아니다.
- Colab 종료 시 새 A100 80GB 런타임에서 노트북을 실행한다. 필요한 `HF_TOKEN`은 Colab 보안 비밀로 제공한다. 새 서버의 연결 파일을 Codespaces의 Git 제외 경로 `workspace/llm_connection.json`에 넣는다.
- 연결 파일 필드: `base_url`(끝에 `/v1`), `model`, `api_key`. 실제 키·토큰은 이 문서와 ZIP에 포함하지 않았다.
- `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY` 환경변수도 지원한다. 환경변수와 연결 파일의 충돌을 확인한다. `.env.example`은 자동 로드되지 않는다.

```bash
python scripts/select_llm_model.py
python scripts/select_llm_model.py google/gemma-4-26B-A4B-it
```

목록 조회만으로 정상 추론이라고 판단하지 말고 실제 짧은 생성도 확인한다. 종료 당시 기본 모델과 `credit-sft-bundle`, `credit-sft-full`, `credit-sft-refined`를 제공했으나 새 환경의 정확한 이름은 목록에서 확인한다. 기본 모델을 선택해 시작한다.

어댑터 서버 복원은 `training/credit_lora/README.md`와 `serve_adapter.py`의 사용법을 따른다. 새 환경에는 이전 비밀 복구 명령이 없을 수 있으므로 노트북으로 기본 서버를 먼저 준비한다. `restore_args.json`, 연결 파일, API 키 및 원시 서버 시작 로그는 Git·공유 백업에 넣지 않는다.

종료 당시 LLM/추론 터널/Streamlit은 유지했고 임시 백업 서버·터널과 GPU 표본 수집기만 중지했다. **현재 접속 가능하다는 뜻은 아니다.**

## 4. 비공개 자료 복구

공개 저장소에는 실제 기업 PDF, 생성 보고서, 학습 데이터, 모델, 체크포인트 및 비공개 Drive 파일 링크를 넣지 않는다. 사용자가 받은 `CreditReviewSupportAgent_HANDOVER_2026-09-08.zip`의 한국어 복구 안내와 인수인계서에 자료별 Drive 링크·해시·복구 방법이 있다. 새 PC에 이 ZIP도 함께 옮긴다. Git clone만으로 비공개 실행 데이터가 복원되지는 않는다.

최소 필요 자료는 입력 PDF, 정상 UI 심사건 백업, 최종 기본/LoRA 비교 및 실패 응답, Colab 복구 노트북이다. 대형 학습 체크포인트는 학습을 재개할 때 받는다. 모든 분할 조각과 manifest를 다운로드한 뒤 저장소 루트에서 실행한다.

```bash
python training/credit_lora/split_backup.py join /path/archive.zip.parts.json /path/restored.zip
python scripts/archive_review_runs.py restore /path/restored.zip /path/new_empty_directory
```

두 번째 명령은 중복 제거된 보고서 심사건 아카이브 전용이다. 일반 ZIP 해제만으로 실행 폴더가 복원되지 않는다. 학습 체크포인트에는 이 restore 명령을 사용하지 않는다. 별도 빈 디렉터리에 복원하고 구조를 확인해 배치한다. 각 백업의 manifest로 해시를 검증한다.
## 5. 완료된 구현과 실제 한계

- PDF v0.17 계열 구조화·표 좌표·출처 추적 유지. 연결/별도 재무제표 구역과 주석 문맥 보존을 개선했다.
- 문서 추출·색인·표 조회를 재사용하고 공통 재무 데이터프레임 및 LLM 작성 Python 계산계획을 구성한다. 계산은 격리된 Docker에서 실행하고 판단에 재사용한다.
- 30개 요인을 7개 보고서 목차에 중복 없이 배정하고 목차별로 한 번만 호출한다. F30을 포함한 종합 위험·의견도 해당 목차 호출 안에서 완결한다.
- 호출별 토큰·지연·검토 상태를 기록하고 실패 시 부분 보고서를 보존한다. 화면 진행 문구를 간결하게 바꿨다.
- 빠른 `prepared` 엔진에 모든 요인의 임의 추가 계산 루프가 통합된 것은 아니다. 별도 `queued` 엔진의 전체 action 루프와 혼동하지 않는다.
- PDF 프로세스 병렬화는 실측에서 속도 개선이 없었으므로 기본 1 worker. source-cell-address 실험도 기본 비활성이다.
- 스캔 PDF OCR 품질, Drive 자동 동기화, 웹 검색, 내부 은행 지표 연결은 검증·구현 완료 범위가 아니다.

주요 코드: `src/credit_review/prepared.py`, `prepared_client.py`, `app/workbench.py`. 상세 구조와 테스트 명령은 저장소 README를 먼저 읽는다.

## 6. 속도·품질·학습 판단

| 시험 | 시간 | 결과 |
| --- | --- | --- |
| 최종 정상 UI, 준비된 자료 | 내부 85.58초 | 30개 판단·9회 호출, 내용 오류 잔존 |
| 신규 PDF 시험 중 한 실행 | parent 113.78초 | 30개 판단이지만 별도 검토·Python 계획 빠짐, 품질 실패 |
| 신규 PDF 기본 설정 후속 실행 | parent 107.42초 | 20개 판단에서 timeout, 최종 종합 없음: 미완료 |
| 복원 서버 refined LoRA | parent 107.65초 | 0개 판단, 문장 반복·6,000 토큰 상한 도달 |
| 동일 복원 서버 기본 모델 | parent 91.20초 | 30개 판단·9회 호출, 전문가 품질 미통과 |

parent 시간은 브라우저 업로드/표시 시간을 포함하지 않는다. 조건이 다른 실행을 단순 인과적 개선율로 비교하지 않는다.

SFT: 원본 4,560개 중 34개를 제외해 4,526개 정제. 대표 표본으로 factor/style 192, bundle 120, section 80, full 32 steps, 이후 train-only 혼합 592개로 refinement 80 steps. assistant 답변에만 loss, 원래 archetype split 보존, ALL30·DPO 제외. LoRA rank16, base 미병합. 전체 원본을 모두 학습한 것은 아니며 정제 데이터도 전문가 정답 데이터로 인증되지 않았다.

Drive 복원 체크포인트로 optimizer/scheduler/RNG 포함 step116→120 실제 재개 검증. 최종 refinement step80은 재다운로드·SHA·CRC·optimizer 포함 확인까지만 했고 실제 재개하지 않았다. `best_adapter`와 재학습 복구 checkpoint를 구분한다.

held-out 비교에서 모든 모델에 의미 오류가 남았고, 더 짧은 출력은 동등한 분석 깊이의 속도 개선 증거가 아니다. 사용한 test 자료를 추가 학습에 넣지 않았으며 향후 모델 선택에는 새로운 미사용 사례가 필요하다.

## 7. 다음 작업 우선순위와 완료 기준

1. 보증 제공/수취 방향, 통화·단위·배수, 기간·연결/별도 범위를 주요 주장마다 원문 셀 또는 실행 계산에 연결한다. 숫자가 입력에 있다는 검사만으로 의미 정확성을 인정하지 않는다.
2. 만기별 계약 현금흐름과 장부 잔액을 구분하고, 근거 없는 상환 안심 표현을 막는다. prepared 경로에 요인별 부족 계산 요청→Python 실행→공통 결과 재사용을 구현한다.
3. 실제 여신 신청금액·용도·기간·상환구조·보증·약정 등 거래 자료를 반영한다. 사업보고서만으로 없는 은행 거래 조건을 만들어 넣지 않는다.
4. 새 사례의 원문 대조·수치 재계산·인과 설명·상환능력·종합 판단을 평가한 뒤 동일 조건의 신규 다중 PDF 및 캐시 실행을 반복 측정한다.

사용자 품질 기준: 업종과 거래에 맞게 분석하되, **근거 → 계산/비교 → 위험과 완화 → 상환능력 → 거래 조건/종합 판단**을 연결한다. 30개 요인은 내부 분석 축이고 화면 보고서는 기준 이미지와 같은 7개 고정 대목차를 사용한다. 각 대목차의 세부 표·항목은 차주·업종·거래 자료에 맞춰 채운다.

공통 검색·재사용 합의: 후속 요청도 기존 LLM 이력·근거·계산·진행 중 동일 요청을 먼저 찾아 중복을 줄이고 부족분만 묶어 처리한다. 기업·기간·범위·단위·자료 버전·검증 상태가 맞아야 재사용한다. 이 전체 흐름이 이미 완성됐다고 가정하지 않는다.

60초는 이전 논의의 목표이며 최종 야간 합의는 전체 보고서 120초다. 첫 토큰·일부 의견·30개 JSON 채움만으로 완료를 선언하지 않는다. 개선 없는 반복은 조기 종료하고 실패 증거를 보존한다. 추가 학습이나 장시간 자동 실행은 새 사용자의 작업 지시에 맞춰 범위를 정한다.

## 8. 참고 문서와 원본 자료

- [최종 야간 결과](OVERNIGHT_RESULTS_2026-09-08.md)
- [SFT 평가](SFT_EVALUATION_2026-09-08.md)
- [학습·서빙·복구 명령](../training/credit_lora/README.md)
- 비공개 인수인계 ZIP의 context/: 상세 품질 기준 및 공통 검색·재사용 합의. 과거 메모의 '아직 학습 승인 전'은 작성 당시 상태이며 최종 결과가 최신이다.
- 비공개 인수인계 ZIP의 reference/: 한국어 복구 안내 및 결과 문서 사본.

예시 보고서 원본 이미지는 ZIP에 포함하지 않았고 별도 Drive 백업 여부도 확인하지 않았다. 원문 품질 재평가에는 사용자 보유 원본이 필요하다. 텍스트 기준만으로 원본 이미지를 검토했다고 주장하지 않는다.
## 9. 새 PC의 Codex에 붙여넣을 시작 문구

> docs/HANDOVER_NEW_PC_2026-09-08.md와 docs/REFERENCE_REPORT_BLUEPRINT.md를 읽고 여신 심사지원 에이전트 작업을 이어가줘. 현재 기본 LIVE 경로는 7개 목차를 순차 순회하며 목차당 LLM 1회, 총 7회만 호출한다. 재추론·후속 호출·별도 최종 종합 호출을 다시 넣지 마. 먼저 개발 브랜치와 현재 Codespaces/Colab 연결 및 Drive 복구 자료를 확인하고, 기본 모델과 실행 중인 LLM 서버를 유지해줘. 다음 목표는 기준 이미지 수준의 표·차트·수치 정확성과 분석 밀도를 로컬 추출·계산·렌더링으로 구현하는 것이다. 과거 5시간 학습 작업을 자동 재개하지 마.
