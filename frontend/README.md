# 여신 심사지원 프론트엔드 v0.1.66

## 배경 유지 및 샘플 의견 HTML v0.1.70

현재 사용자 선택은 배경이 있는 원본 UI이다. `py frontend/build.py` 후 `py frontend/sample-review.py`를 실행하면 `outputs/sample_review_260909/CreditReviewSupportAgent_UI_v0.1.70.html`과 다운로드 사본을 생성한다. v0.1.70은 앱 전용 CSS를 사용하지 않는다.

첨부 35844~35849.jpg의 1~6/7쪽을 읽고 Codex가 작성한 검토용 초안을 담았다. 종합의견1 가~마 및 합본, 종합의견2, 심사보고서 7개 절을 제공한다. 실시간 AI API 실행 결과가 아니며 외부 최신정보를 검증하지 않았다. 원문 이미지 6장은 HTML에 내장되어 더보기 메뉴에서 볼 수 있다. 미해결 수치 충돌은 금액 검수 결과에 별도로 보존한다.

최초 열기에만 고유 샘플 심사건과 프롬프트를 등록한다. 같은 출처에서 재열기 시 기존 수정 내용을 덮어쓰지 않는다. `CreditReview.installPromptPack({view_id: text})`는 현재 업체에 항목별 프롬프트를 추가하며 다른 업체의 공통 설정을 변경하지 않는다. `generationPrompts()`는 현재 화면에서 편집한 값을 포함한 8개 화면 프롬프트를 반환한다. `analyze` 요청에는 `generation_prompts`가 포함되며 서버 어댑터가 이를 실제 모델 입력에 반영해야 한다. 현재 서버 연결은 별도로 필요하다.

`sample-check.html` 검증은 동일 폴더의 `sample170.html`을 대상으로 실행한다. 8개 화면 본문·상태, 원문 6장, 보고서 7개 절, 프롬프트 등록, 모의 analyze 요청 전달, 재열기 보존을 확인한다. 모의 요청 검증은 실제 AI 실행 검증이 아니다.

## 앱 화면 HTML v0.1.69

`CreditReviewSupportAgent_App_v0.1.69.html`은 원본 상단 확대·복원 버튼으로 두 모드를 전환합니다. 기본 메신저 화면은 470×720px이며 작은 화면에서는 사용 가능한 영역에 맞춥니다. 확대하면 브라우저 Fullscreen API로 전체화면 작업 UI를 표시하고 복원하면 작은 메신저 화면으로 돌아옵니다. 자동 너비 전환은 하지 않습니다. 회색 미리보기 배경과 하단 실행 아이콘, 가짜 최소화·닫기 버튼은 제거했습니다. 일반 브라우저 탭에서는 HTML 영역만 줄어들며 브라우저 창 자체의 크기는 바뀌지 않습니다. Chrome의 `--app` 바로가기로 실행하면 주소창 없는 작은 창에서 사용할 수 있습니다. HTML만으로 동작하며 기존 API 연결·저장 기능은 동일합니다. `app.css`와 `app.js`를 수정한 후 같은 빌드 명령으로 생성합니다.

`CreditReviewSupportAgent_UI_v0.1.66.html`은 원본 v0.1.65의 기본창·전체화면 디자인을 사용하는 독립 HTML입니다. Streamlit/Colab 서버를 변경하거나 배포하지 않습니다. 기본값은 AI 미연결이며 샘플 추론으로 본문을 수정하지 않습니다.

## 실행과 수정

```powershell
py -m http.server 8765 --bind 127.0.0.1 --directory frontend
```

브라우저에서 `http://127.0.0.1:8765/CreditReviewSupportAgent_UI_v0.1.66.html`을 엽니다. 파일 직접 열기보다 localhost 또는 실제 서비스의 동일 출처 URL을 사용하세요. IndexedDB는 출처별 저장소이므로 호스트·포트가 바뀌면 다른 작업 공간입니다. 다른 PC로 자동 동기화되지는 않습니다.

- `source/original.html`: 사용자 원본. 수정하지 않는 화면 기준입니다.
- `source/operating.html`: 원본 내부 전체화면 HTML을 추출한 화면 기준입니다.
- `bridge.js`: 기본창 상태, 브라우저 저장, API 계약, 문장·표·근거 처리.
- `frame.js`: 전체화면을 부모 상태에 연결하는 어댑터. 독립 API 호출을 하지 않습니다.
- `build.py`: 두 어댑터와 화면 기준을 독립 HTML 하나로 묶습니다.
- `check.html`: 가상 데이터·가상 transport를 사용하는 브라우저 통합 검사입니다. 실제 LLM 호출이 아닙니다.

수정 후 `py frontend/build.py`로 다시 생성합니다. 생성 HTML을 직접 편집하면 다음 빌드에 덮어써집니다. 검증 페이지는 임시로 IndexedDB를 사용한 후 원래 스냅샷을 복원합니다. 별도 브라우저 출처에서 실행하세요.

## 공통 데이터와 저장

업체는 UUID 또는 서버 case ID, 화면은 아래 고정 ID, 문장은 `data-paragraph-id`를 사용합니다. 배열 순서나 한국어 항목명을 서버 식별자로 쓰지 않습니다.

| 화면 | view_id |
|---|---|
| 종합의견1 | summary_1 |
| 가. 재무제표 주요계정 | financial_accounts |
| 나. 수익성 | profitability |
| 다. 재무안정성 및 자산의 질 | financial_stability |
| 라. 현금흐름 및 재무상환능력 | cashflow_repayment |
| 마. 주요 매출처 및 매출비중 변동 추이 | customer_concentration |
| 종합의견2 | summary_2 |
| 심사보고서 | report |

종합의견1은 가~마의 표시용 합본입니다. 기본창과 전체화면이 같은 메모·대화·본문을 사용합니다. 자동 저장은 IndexedDB에 파일 Blob까지 보존합니다. API 자격증명은 저장하지 않습니다. 저장 실패는 화면에 알립니다. 중요한 작업은 저장 메뉴로 완료를 확인하세요. 웹사이트 데이터 삭제는 이 브라우저의 보관 데이터도 제거합니다.

표·문단·출처는 구조적으로 보존됩니다. 금액 감사 목록은 본문에 적용하지 않습니다. 보고서의 서버 반환 원본은 `records[].report`에 별도로 보관합니다. 수정된 화면 문구와 서버 원본을 구분하세요.

## API 연결

HTML의 마지막에 서비스 초기화 스크립트를 붙이거나 `credit-review:ready` 이벤트에서 설정합니다.

```js
await CreditReview.ready;
CreditReview.configure({baseUrl: '/api/credit-review/v1/'});
await CreditReview.loadCase({id: 'case-001', name: '업체명', revision: 1});
await CreditReview.refresh();
```

`configure`는 주소 설정이며 실제 서버 연결 성공을 의미하지 않습니다. 인증은 동일 출처의 서버 세션 쿠키로 처리합니다. 임의의 외부 주소나 URL 쿼리의 토큰은 받지 않습니다. 기존 Python 엔진과 이 계약을 연결하는 API 서버는 별도 구현 대상입니다. 현재 저장소에는 아래 엔드포인트가 없습니다.

모든 작업은 `POST {baseUrl}/{operation}`입니다. JSON 요청에는 `case_id`, `run_id`, `view_id`, `base_revision`이 포함됩니다. `X-Request-ID`가 붙고, revision이 있으면 `If-Match`를 전송합니다. 서버는 인증·심사건 접근 권한·revision 비교·요청 중복 처리를 수행해야 합니다. 409/412는 화면에서 충돌로 표시하며 강제 덮어쓰지 않습니다.

| operation | 추가 입력 | 반환 |
|---|---|---|
| state | 공통 문맥 | 아래 loadCase 형식 |
| chat | request, paragraphs, common_prompt, notes, prompts | `{message, revision?}` |
| revise | chat과 동일 | `{replacements: [{id, text}], message?, revision?}` |
| upload | multipart: file와 JSON 문자열 metadata | `{document_id}` |
| analyze | documents: `[{id, description, priority, required}]`, outline, common_prompt | `{id, status, ...}` 실행 상태 |
| save | workspace: 스냅샷 | `{revision}` |

대용량 분석은 analyze에서 실행 ID를 빠르게 반환하고, `분석 결과 불러오기`로 state를 조회하는 계약입니다. 자동 폴링·백그라운드 분석·자동 재시도는 하지 않습니다. 업로드 허용 형식은 현재 백엔드와 같은 PDF·JSON, 파일당 200MB입니다. 서버에서도 같은 제한을 검사해야 합니다. save의 JSON에는 파일 본문이 포함되지 않으므로 파일은 upload로 보관하고 `server_id`를 연결해야 합니다.

기존 서버에 맞춰 경로·인증 방식을 바꾸려면 HTTP 기본 구현 대신 transport를 주입할 수 있습니다.

```js
CreditReview.configure({
  transport: async (operation, payload) => {
    // 서비스의 실제 API에 연결하고 위 반환 형식으로 변환합니다.
    // upload payload.file은 Blob/File이며, 다른 payload는 구조화 데이터입니다.
    return yourBackendAdapter(operation, payload);
  }
});
```

## 보고서 수신 예

```js
await CreditReview.loadCase({
  id: 'case-001', name: '업체명', revision: 2,
  report: {
    case_id: 'case-001', draft: true,
    sections: [{title: '재무 분석', paragraphs: [
      {id: 'paragraph-001', heading: '수익성', text: '근거에 따른 분석 문구',
       sources: [{id: 'doc-1-page-3', label: '사업보고서 3쪽'}]}
    ], tables: [{caption: '재무현황', columns: ['연도', '매출액'],
      rows: [['2025', '100억원']], after_paragraph_index: 0}]}]
  },
  views: {
    profitability: {paragraphs: [{id: 'paragraph-001', heading: '수익성',
      text: '근거에 따른 분석 문구'}], tables: []}
  },
  audit: [{path: '/sections/0', old: '100억원', new: '101억원', reason: '원문 대조 필요'}]
});
```

현재 엔진의 7개 목차는 report 화면에 모두 표시합니다. 가~마 화면에 배치할 내용은 서버가 `views`에 명시해야 합니다. 기존 엔진의 재무 분석을 임의로 수익성·안정성 등으로 잘라 넣지 않습니다. `coverage`는 원본 UI의 6개 그룹×각 5항목의 boolean 배열을 명시적으로 제공할 수 있으며, 백엔드 F01~F30과의 의미 대응은 서버에서 정의해야 합니다.

서버 문구는 텍스트로 렌더링하며 스크립트·이벤트 속성·임의 URL은 제거합니다. 보완은 기존 문장 ID에 대한 교체만 허용하고, 모르는 ID·중복 ID·빈 문장은 응답 전체를 거절합니다. 보완 전 사용자 확인, 처리 중 이동 방지, 전후 버전 비교를 제공합니다. 금액 감사 자동 반영과 최종 승인 기능은 연결하지 않습니다.
