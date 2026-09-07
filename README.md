# CreditReviewSupportAgent

Codespaces 단계형 기업여신 심사 테스트 하네스. Colab은 LLM 서버이며 기존 운영/HTML 자산은 포함하지 않습니다.

## 실행

```bash
pip install -e '.[test]'
docker build -f docker/calculator.Dockerfile -t credit-review-calculator:0.1 .
python -m streamlit run app/workbench.py --server.address 0.0.0.0
```

Codespaces Ports → 8501 → Open in Browser. 포트는 Private으로 유지합니다.
자료 업로드 후 **분석 시작**을 누르면 요인별 분석과 계산을 거쳐 심사보고서를 작성합니다. 화면과 다운로드에는 보고서 본문·표만 표시하며 누락/충돌/coverage/실행 기록은 내부 JSON에 보존합니다. 생성 전 LLM 연결을 확인하며 연결 실패를 분석 완료로 표시하지 않습니다.
기존에 저장된 DEMO 보고서는 가상 자료와 사전 정의 JSON으로 만든 예시입니다. 실제 LLM 분석이 아닙니다.

## Colab 연결

실행 전 Codespaces 환경에 `LLM_BASE_URL` (끝에 /v1), `LLM_MODEL`, `LLM_API_KEY`를 설정합니다.
`.env.example`은 예시이며 자동 로드되지 않습니다. 키는 Git에 저장하지 않습니다.
기본 화면은 prepared 엔진을 사용합니다. 원문을 구조화하고 공통 재무 데이터프레임과 Python 계산을 만든 뒤 요인을 묶어 분석하고 보고서를 스트리밍합니다. 별도 queued 엔진에는 search/read/dataset/calculate/conclude action 루프가 있습니다. prepared 엔진에 모든 요인별 동적 계산 루프가 통합된 것은 아닙니다.
또는 Git에서 제외되는 `workspace/llm_connection.json`에 `base_url`, `model`, `api_key`를 저장하면 서버 재시작 없이 다음 요청에서 읽습니다. 키가 포함된 이 파일을 공유하거나 Git에 올리지 않습니다.

## 구현

- 30개 요인별 상태, 근거 요건 및 누락/충돌 관리
- LLM JSON → 유연한 데이터 표 → DataFrame → LLM Python 코드 → 실행 결과 → 요인 판단
- 원문 및 셀별 출처 참조, 공표일 필터, 반복 검색 및 부모 문맥 조회
- 문자 n-gram 검색 + 선택적 CPU 임베딩 + reciprocal rank fusion
- networkless/read-only Docker 계산, 시간·메모리·프로세스 제한
- 입력/출력 불변 JSON, 실행 이력, 요인 재시작, 디스크 재개
- 요인별 분석과 검토용 종합 초안, JSON/Markdown 다운로드

## 현재 한계

- 실제 Colab Gemma 서버와 PDF 보고서 생성을 시험했습니다. 캐시 자료는 여러 시험에서 2분 이내에 작성됐지만, 최초 PDF 처리까지 포함한 시험은 완료와 부분 중단이 모두 발생했습니다. 제공된 예시 수준의 심사 품질과 안정적인 2분 완료를 함께 달성하지는 못했습니다. [야간 작업 결과](docs/OVERNIGHT_RESULTS_2026-09-08.md)에 조건과 한계를 기록했습니다.
- 현재 검증은 스키마·참조 무결성·기준일·실행 오류 중심입니다. 수치 원문 일치, 산식 의미, 주장 진실성의 완전한 자동 검증은 후속 연결 대상입니다. 보고서는 항상 DRAFT입니다.
- 임베딩 미설정 시 화면에 lexical_only로 표시합니다. 선택적 모델은 `pip install -e '.[embedding]'` 후 지정합니다. 영구 벡터 캐시·학습형 reranker는 후속 작업입니다.
- PDF는 기존 v0.17 계열 구조화 로직을 재사용하며 표 위치·헤더·본문과 연결/별도 재무제표 구역을 보존합니다. 이번 실측은 텍스트 PDF이며, 스캔 이미지의 LLM OCR 품질 검증은 포함하지 않습니다. 기존 운영 추론 엔진 전체를 통합한 상태는 아닙니다.
- 새 자료는 새 run으로 등록합니다. 요인 재시작은 기존 입력과 이력을 보존하고 공통 근거·계산 결과를 재사용합니다. 자료 변경 시 모든 종속 판단의 자동 갱신은 추가 검증 대상입니다.
- Drive 자동 동기화·웹 검색·내부 지표 연결은 미구현입니다. 자료는 업로드로 등록합니다.

## JSON 자료 형식

```json
{"sources":[{"id":"doc1_p1","document_id":"doc1","page":1,"published_at":"2026-03-31","kind":"page","text":"원문 내용","metadata":{}}]}
```

id는 고유하고 공표일은 확인된 날짜여야 합니다. parent_id로 표/절/페이지 관계를 연결합니다.
실행 데이터는 Git 제외 경로 `workspace/cases/{case_id}/runs/{run_id}/`의 state.json, events.jsonl, artifacts/, datasets/에 저장합니다.
원본/실행 보존 자료는 Drive, 코드/설정은 GitHub, 작업 사본/캐시는 Codespaces에 두는 방향입니다.

## 검증

```bash
pytest -q
```

가상 흐름, 저장/재개, 미래자료 제외, 출처 오류, 연결/별도 구역, 잘못된 JSON, 반복 종료, 화면 초기 로딩을 검증합니다. 실제 보고서 시험에서 Docker Python 계산 실행도 확인했습니다. 스키마·참조 검증 통과는 심사 내용의 정확성 인증이 아닙니다.

## v1 및 LoRA

첫 1시간의 비교 기준은 변경하지 않는 `v1` 태그에 보관합니다. 이후 수정은 `codex/credit-review-harness`에 있습니다. LoRA는 기본 가중치에 병합하지 않고 요청 모델명으로 선택합니다. 기본값은 Gemma 원본이며, 학습 완료만으로 어댑터를 운영용으로 승격하지 않습니다.

- [SFT 데이터·학습·복구 안내](training/credit_lora/README.md)
- [기본 모델/어댑터 평가](docs/SFT_EVALUATION_2026-09-08.md)
- [5시간 작업 결과 및 남은 과제](docs/OVERNIGHT_RESULTS_2026-09-08.md)

학습 데이터·가중치·실제 기업 자료·실행 기록은 Git에 넣지 않습니다. 이들의 Drive 백업과 코드 저장소는 별도이며, Drive의 기존 프리징 운영 자산과 HTML은 변경하지 않았습니다.
