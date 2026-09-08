"""Upload -> factor orchestration -> report. Diagnostic state stays on disk."""
import hashlib
import importlib
import json
import os
import traceback
from uuid import uuid4
from datetime import date
from contextlib import ExitStack
from time import monotonic
from time import sleep
from pathlib import Path

import streamlit as st

from credit_review.demo import DemoClient
import credit_review.documents as documents_module
importlib.reload(documents_module)
from credit_review.documents import from_json, from_pdf_isolated as from_pdf
from credit_review.vendor.spt017 import PIPELINE_VERSION
from credit_review.harness import Harness
import credit_review.llm as llm_module
import credit_review.models as models_module
import credit_review.harness as harness_module
import credit_review.reporting as reporting_module
import credit_review.retrieval as retrieval_module
import credit_review.table_access as table_access_module

# Streamlit preserves imported modules between reruns. Refresh the small,
# stateless client so a deployed connection fix applies without losing uploads.
importlib.reload(models_module)
import credit_review.batch_protocol as batch_protocol_module
importlib.reload(batch_protocol_module)
ColabClient = importlib.reload(llm_module).ColabClient
importlib.reload(table_access_module)
importlib.reload(retrieval_module)
Harness = importlib.reload(harness_module).Harness
importlib.reload(reporting_module)
import credit_review.parallel as parallel_module
importlib.reload(parallel_module)
from credit_review.parallel import analyse_factors, run_lease, Measurements, MeasuredClient
import credit_review.grouped as grouped_module
importlib.reload(grouped_module)
import credit_review.queued as queued_module
importlib.reload(queued_module)
from credit_review.grouped import analyse_grouped
import credit_review.prepared as prepared_module
importlib.reload(prepared_module)
import credit_review.prepared_client as prepared_client_module
importlib.reload(prepared_client_module)
from credit_review.prepared import analyse_prepared
from credit_review.ingestion import prepare_upload
from credit_review.store import atomic_json
from credit_review.registry import FACTORS
from credit_review.reporting import report_document, report_markdown
from credit_review.store import identifier
from credit_review.run_health import checkpoint, saved_status, status_message, service_failure, explain_failure

ROOT = Path(os.environ.get("CREDIT_WORKSPACE", "workspace"))

class LazyLiveClient:
    model = os.environ.get("LLM_MODEL", "")
    def next_action(self, context):
        return ColabClient().next_action(context)
    def synthesize(self, context):
        return ColabClient().synthesize(context)
    def next_actions(self, context):
        return ColabClient().next_actions(context)
    def stream_report(self, context):
        yield from ColabClient().stream_report(context)

def load_report(path):
    meta = json.loads(path.read_text(encoding="utf-8"))
    client = DemoClient() if meta["mode"] == "DEMO" else LazyLiveClient()
    return Harness.resume(ROOT, meta["case_id"], meta["run_id"], client)

def show_report(h):
    if h is None:
        st.title("주요여신위험 및 종합심사의견")
        st.caption("자료를 업로드한 뒤 분석 시작을 누르면 심사보고서가 작성됩니다.")
        return
    report = report_document(h)
    st.markdown(report_markdown(report))
    if not report["sections"]:
        st.caption("아직 작성된 보고서가 없습니다.")

st.set_page_config(page_title="기업여신 심사보고서", layout="wide")

# Keep controls in a fixed left rail and reserve matching report space.
st.markdown(
    """
    <style>
    :root { --review-sidebar-width: clamp(230px, 28vw, 300px); }
    [data-testid="stAppViewContainer"] { min-width: 0 !important; }
    section[data-testid="stSidebar"] {
        position: fixed !important;
        inset: 0 auto 0 0 !important;
        width: var(--review-sidebar-width) !important;
        min-width: var(--review-sidebar-width) !important;
        transform: none !important;
        z-index: 100 !important;
        border-right: 1px solid rgba(49, 51, 63, 0.16);
    }
    section[data-testid="stSidebar"] > div:first-child {
        height: 100vh;
        overflow-y: auto;
    }
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"] { display: none !important; }
    .main,
    [data-testid="stMain"] {
        margin-left: var(--review-sidebar-width) !important;
        width: calc(100% - var(--review-sidebar-width)) !important;
        min-width: 0 !important;
    }
    .main .block-container,
    [data-testid="stMainBlockContainer"] {
        max-width: none !important;
        padding: 2rem 1.5rem 4rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
if st.query_params.get('benchmark') == 'latest':
    import credit_review.live_view as live_view_module
    importlib.reload(live_view_module)
    from credit_review.live_view import latest_snapshot
    @st.fragment(run_every=1)
    def live_benchmark_report():
        snapshot = latest_snapshot(ROOT, st.query_params.get('run'))
        if snapshot is None:
            st.info('보고서 작성을 준비하고 있습니다. 결과는 자동으로 표시됩니다.')
            return
        if snapshot['active']:
            st.info('심사보고서 작성 중 · 생성되는 의견이 자동으로 표시됩니다.')
        elif snapshot['finished']:
            st.success('심사보고서 작성이 완료되었습니다.')
        else:
            st.warning('이번 실행이 종료되었습니다. 현재까지 작성된 의견을 표시합니다.')
        st.markdown(snapshot['report'])
        if not snapshot['active']:
            st.download_button('심사보고서 다운로드',snapshot['report'],'credit_review_report.md',mime='text/markdown')
        if not snapshot['opinions']:
            st.caption('자료를 분석하고 있습니다. 첫 의견을 기다리는 중입니다.')
    live_benchmark_report()
    archive=ROOT/'benchmarks'/'overnight_v1_evidence.zip'
    if st.query_params.get('archive')=='1' and archive.exists():
        st.download_button('검증 기록 다운로드',archive.read_bytes(),archive.name,mime='application/zip')
    st.stop()
saved = sorted(ROOT.glob("cases/*/runs/*/state.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
if "harness" not in st.session_state and saved:
    try:
        st.session_state.harness = load_report(saved[0])
    except Exception:
        pass

with st.sidebar:
    st.subheader("심사 자료")
    if saved:
        selected = st.selectbox("저장된 보고서", saved, format_func=lambda p: f"{p.parents[2].name} · {p.parent.name[-8:]}")
        if st.button("보고서 열기"):
            try:
                st.session_state.harness = load_report(selected)
                st.session_state.pop("generation_message", None)
                st.rerun()
            except Exception:
                st.error("저장된 보고서를 열 수 없습니다.")
    upload = st.file_uploader("자료 업로드", type=["pdf", "json"], accept_multiple_files=True)
    case_id = st.text_input("심사건 이름", "case_001")
    cutoff = st.date_input("심사 기준일", date(2026, 4, 7))
    published = st.date_input("자료 공표일", date(2026, 3, 31))
    start = st.button("분석 시작", type="primary", disabled=not upload)
    resume = st.button("보고서 작성 계속", disabled="harness" not in st.session_state)
    message = st.session_state.get("generation_message")
    message_area = st.empty()
    if message and not (start or resume):
        message_area.error(message)
    else:
        message_area.empty()

# Start expensive preparation on upload, before the employee requests analysis.
preparation = [(file.name, prepare_upload(ROOT, file.getvalue(), file.name, published, retry=start))
               for file in upload]

@st.fragment(run_every=1)
def preparation_status():
    if not preparation:
        return
    ready = sum(f.done() and f.exception() is None for _, f in preparation)
    failed = sum(f.done() and f.exception() is not None for _, f in preparation)
    if failed:
        st.caption('일부 자료 준비에 실패했습니다. 분석 시작 시 재시도합니다.')
    elif ready == len(preparation):
        st.caption(f'자료 {ready}개 준비 완료')
    else:
        st.caption(f'본문·표 준비 중: {ready}/{len(preparation)}개 완료')

with st.sidebar:
    preparation_status()

h = st.session_state.get("harness")
if h:
    # Rehydrate persisted state after deployments; retain uploaded browser files.
    h = load_report(h.store.path / "state.json")
    st.session_state.harness = h
outcome_area = st.empty()
report_area = st.empty()
if h and not (start or resume):
    outcome = saved_status(h)
    if outcome:
        if outcome['status'] in ('FAILED', 'PARTIAL'):
            outcome_area.warning(status_message(outcome))
        elif outcome['status'] == 'COMPLETED':
            outcome_area.success('이번 보고서 작성이 완료되었습니다. 검토용 초안이 저장되었습니다.')
        else:
            outcome_area.info(status_message(outcome) + '\n\n완료 기록이 없습니다. 실행이 멈췄다면 이어서 작성할 수 있습니다.')
with report_area.container():
    show_report(h)

if start or resume:
    # Check service before accepting a new run. Do not silently create a zero-result case.
    live = start or (h and h.state.mode == "LIVE")
    stage, current_question = "LLM 서버 연결 확인", ""
    if resume and h:
        previous = saved_status(h)
        current_question = previous.get("question", "") if previous else ""
        if not current_question:
            current_question = next((f.inquiry.question for f in h.state.factors.values() if f.inquiry and not f.judgement), "")
    lease_stack = ExitStack()
    owns_run = False
    metrics = Measurements()
    try:
        if h and resume:
            lease_stack.enter_context(run_lease(h))
            owns_run = True
        if h and owns_run:
            checkpoint(h, "RUNNING", stage)
        if live:
            client = ColabClient()
            client.check()
        else:
            client = DemoClient()
        if start:
            stage = "PDF 본문 및 표 구조 분석"
            identifier(case_id)
            sources = []
            input_hashes = set()
            for name, future in preparation:
                waiting = monotonic()
                while not future.done():
                    outcome_area.info(f'{name}의 본문·표를 준비하고 있습니다. 준비 완료 후 분석을 시작합니다.')
                    sleep(0.3)
                prepared = future.result()
                metrics.record('preparation_wait', waiting, prepared['cached'])
                if prepared['document_hash'] in input_hashes:
                    continue
                input_hashes.add(prepared['document_hash'])
                sources.extend(from_json(json.dumps({'sources':prepared['sources']}).encode()))
            if not sources or not any(s.text.strip() and s.published_at <= cutoff for s in sources):
                raise ValueError("No readable evidence within review date")
            if len({s.id for s in sources}) != len(sources):
                raise ValueError("Duplicate evidence IDs")
            h = Harness.create(ROOT, case_id, cutoff, sources, client, "LIVE", os.environ.get("EMBEDDING_MODEL", ""))
            h.state.review_strategy = 'grouped'
            h.save()
            st.session_state.harness = h
        else:
            h.client = client
        if not owns_run:
            lease_stack.enter_context(run_lease(h))
            owns_run = True
        h.client = MeasuredClient(client, metrics)
        st.session_state.pop("generation_message", None)
        progress = st.empty()
        activity = outcome_area
        writing = st.empty()
        def status(action, question):
            global stage, current_question
            labels = {"plan": "검토 질문과 확인 계획을 세우고 있습니다", "reframe": "검토 방향을 조정하고 있습니다",
                "search": "관련 근거를 검색하고 있습니다", "read": "원문과 주석을 확인하고 있습니다",
                "dataset": "계산에 필요한 자료를 구성하고 있습니다", "calculate": "Python으로 계산하고 있습니다",
                "conclude": "근거를 종합해 판단을 정리하고 있습니다"}
            stage, current_question = labels.get(action, '판단 검토'), question
            checkpoint(h, "RUNNING", stage, question)
            activity.info(f"{question}\n\n{stage}.")
        def write_section(fid=None):
            global stage
            stage = "종합심사의견 본문 출력" if fid is None else f"{FACTORS[fid]['name']} 본문 출력"
            checkpoint(h, "RUNNING", stage, current_question)
            activity.info("종합심사의견을 작성하고 있습니다." if fid is None else f"{FACTORS[fid]['name']} 판단을 보고서로 작성하고 있습니다.")
            try:
                with writing.container():
                    st.caption("작성 중인 보고서 초안")
                    if fid is None and live:
                        client.set_deadline(metrics.started + 120)
                        st.write_stream(h.stream_synthesis())
                    else:
                        st.write_stream(h.stream_narrative(fid))
            except Exception as error:
                h.store.event(action="narrative", factor_id=fid, status="ERROR", error=str(error))
                raise
            finally:
                writing.empty()
                with report_area.container():
                    show_report(h)
        targets = ["F24"] if h.state.mode == "DEMO" else list(FACTORS)
        with st.spinner("심사보고서를 작성하고 있습니다."):
            questions = {}
            # LIVE runs use dependency-aware waves: seven rendered sections,
            # with finance split into two calls to stay within model context.
            if live:
                h.state.review_strategy = 'hybrid_sections'
                h.save()
            engine = analyse_prepared if live else analyse_factors
            for event in engine(h, targets, concurrency=int(os.environ.get('CREDIT_SECTION_CONCURRENCY','2')), metrics=metrics,
                                **({'time_budget':int(os.environ.get('CREDIT_ANALYSIS_TIME_BUDGET','900'))} if live else {})):
                kind, fid = event['kind'], event.get('factor_id')
                if kind == 'status':
                    value = event['value']
                    labels = {'plan':'검토 계획', 'reframe':'접근 재정의', 'search':'근거 검색',
                              'read':'원문 확인', 'dataset':'자료 구성', 'reuse':'검증된 자료 재사용',
                              'calculate':'Python 계산', 'conclude':'판단 정리', 'review':'판단 중'}
                    questions[fid] = value['question'] + ' — ' + labels.get(value['action'], '검토 중')
                    stage, current_question = '요인별 근거 검토', value['question']
                    checkpoint(h, 'RUNNING', stage, current_question)
                elif kind == 'done':
                    questions.pop(fid, None)
                if kind in ('state', 'done'):
                    with report_area.container():
                        show_report(h)
                elapsed = int(event['metrics']['elapsed_seconds'])
                # Analysis artifacts stay on disk; keep live status compact above the report.
                text = '\n\n'.join(list(questions.values())[:2])
                if len(questions) > 2:
                    text += f"\n\n이 목차의 나머지 {len(questions)-2}개 항목을 함께 작성하고 있습니다."
                activity.info(f"{text or '다음 검토를 준비하고 있습니다.'}\n\n경과 {elapsed//60}분 {elapsed%60}초")
                if 'finished' in event:
                    progress.progress(event['finished']/event['total'], text='심사보고서 작성 중')
            if not any(f.judgement for f in h.state.factors.values()):
                errors = [f.error for f in h.state.factors.values() if f.error]
                raise RuntimeError(errors[-1] if errors else "Analysis validation failed: no supported judgements")
        incomplete = [f for f in h.state.factors.values() if not f.judgement]
        checkpoint(h, "PARTIAL" if incomplete else "COMPLETED", "보고서 저장", reason=
            "일부 요인 분석이 검증 또는 실행 한도에서 종료되어 부분 보고서로 저장했습니다." if incomplete else "")
        progress.empty()
        activity.empty()
    except Exception as error:
        atomic_json(ROOT / 'failures' / (uuid4().hex + '.json'), {
            'stage': stage, 'error_type': type(error).__name__,
            'error': str(error), 'traceback': traceback.format_exc(),
        })
        if h and owns_run:
            h.store.event(action="report_generation", status="ERROR", error=str(error))
            checkpoint(h, "FAILED", stage, current_question, explain_failure(error))
        st.session_state.generation_message = stage + ': ' + explain_failure(error)
    except BaseException:
        if h and owns_run:
            checkpoint(h, "FAILED", stage, current_question,
                       "화면 실행이 중단되었습니다. 저장된 판단을 유지했으며 이어서 작성할 수 있습니다.")
        raise
    finally:
        if metrics and h and owns_run:
            atomic_json(h.store.path/'performance.json', metrics.snapshot())
        lease_stack.close()
    st.rerun()

if h and report_document(h)["sections"]:
    st.download_button("심사보고서 다운로드", report_markdown(report_document(h)), "credit_review_report.md", mime="text/markdown")
