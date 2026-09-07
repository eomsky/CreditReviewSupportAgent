"""Upload -> factor orchestration -> report. Diagnostic state stays on disk."""
import hashlib
import importlib
import json
import os
from datetime import date
from pathlib import Path

import streamlit as st

from credit_review.demo import DemoClient
from credit_review.documents import from_json, from_pdf
from credit_review.harness import Harness
import credit_review.llm as llm_module
import credit_review.models as models_module
import credit_review.harness as harness_module
import credit_review.reporting as reporting_module

# Streamlit preserves imported modules between reruns. Refresh the small,
# stateless client so a deployed connection fix applies without losing uploads.
importlib.reload(models_module)
ColabClient = importlib.reload(llm_module).ColabClient
Harness = importlib.reload(harness_module).Harness
importlib.reload(reporting_module)
from credit_review.registry import FACTORS
from credit_review.reporting import report_document, report_markdown
from credit_review.store import identifier

ROOT = Path(os.environ.get("CREDIT_WORKSPACE", "workspace"))

class LazyLiveClient:
    model = os.environ.get("LLM_MODEL", "")
    def next_action(self, context):
        return ColabClient().next_action(context)
    def synthesize(self, context):
        return ColabClient().synthesize(context)
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
    if message and not (start or resume):
        st.error(message)

h = st.session_state.get("harness")
if h:
    # Rehydrate persisted state after deployments; retain uploaded browser files.
    h = load_report(h.store.path / "state.json")
    st.session_state.harness = h
report_area = st.empty()
with report_area.container():
    show_report(h)

if start or resume:
    # Check service before accepting a new run. Do not silently create a zero-result case.
    live = start or (h and h.state.mode == "LIVE")
    try:
        if live:
            client = ColabClient()
            client.check()
        else:
            client = DemoClient()
        if start:
            identifier(case_id)
            sources = []
            for file in upload:
                if file.name.lower().endswith(".json"):
                    sources.extend(from_json(file.getvalue()))
                else:
                    folder = ROOT / "cases" / case_id / "sources"
                    folder.mkdir(parents=True, exist_ok=True)
                    path = folder / (hashlib.sha256(file.getvalue()).hexdigest() + ".pdf")
                    path.write_bytes(file.getvalue())
                    sources.extend(from_pdf(path, published))
            if not sources or not any(s.text.strip() and s.published_at <= cutoff for s in sources):
                raise ValueError("No readable evidence within review date")
            if len({s.id for s in sources}) != len(sources):
                raise ValueError("Duplicate evidence IDs")
            h = Harness.create(ROOT, case_id, cutoff, sources, client, "LIVE", os.environ.get("EMBEDDING_MODEL", ""))
            st.session_state.harness = h
        else:
            h.client = client
        st.session_state.pop("generation_message", None)
        progress = st.empty()
        activity = st.empty()
        writing = st.empty()
        def status(action, question):
            labels = {"plan": "검토 질문과 확인 계획을 세우고 있습니다", "reframe": "검토 방향을 조정하고 있습니다",
                "search": "관련 근거를 검색하고 있습니다", "read": "원문과 주석을 확인하고 있습니다",
                "dataset": "계산에 필요한 자료를 구성하고 있습니다", "calculate": "Python으로 계산하고 있습니다",
                "conclude": "근거를 종합해 판단을 정리하고 있습니다"}
            activity.info(f"{question}\n\n{labels.get(action, '판단을 검토하고 있습니다')}.")
        def write_section(fid=None):
            activity.info("종합심사의견을 작성하고 있습니다." if fid is None else f"{FACTORS[fid]['name']} 판단을 보고서로 작성하고 있습니다.")
            try:
                with writing.container():
                    st.caption("작성 중인 보고서 초안")
                    st.write_stream(h.stream_narrative(fid))
            except Exception as error:
                h.store.event(action="narrative", factor_id=fid, status="ERROR", error=str(error))
                activity.info("본문 출력이 중단되어 확보된 판단을 표시합니다.")
            finally:
                writing.empty()
                with report_area.container():
                    show_report(h)
        targets = ["F24"] if h.state.mode == "DEMO" else list(FACTORS)
        with st.spinner("심사보고서를 작성하고 있습니다."):
            for i, fid in enumerate(targets):
                factor = h.state.factors[fid]
                if factor.judgement:
                    if live and not factor.report_text:
                        write_section(fid)
                    continue
                if factor.status in ("ERROR", "LIMIT_REACHED", "NO_PROGRESS"):
                    h.reset_factor(fid)
                for _ in range(24):
                    factor = h.state.factors[fid]
                    question = factor.inquiry.question if factor.inquiry else f"{FACTORS[fid]['name']}에서 여신 판단에 중요한 쟁점은 무엇인가?"
                    if factor.status == "RETRYING":
                        activity.info(f"{question}\n\n자료 형식과 검증 결과를 재검토하고 있습니다.")
                    else:
                        status("review", question)
                    factor = h.step(fid, max_steps=24, repair_attempts=2, on_status=status)
                    if factor.judgement or factor.status in ("ERROR", "LIMIT_REACHED", "NO_PROGRESS"):
                        break
                if live and factor.judgement:
                    write_section(fid)
                # Preserve missing/conflict/errors internally. They are not report sections.
                with report_area.container():
                    show_report(h)
                progress.progress((i + 1) / len(targets), text="심사보고서 작성 중")
            if any(f.judgement for f in h.state.factors.values()):
                try:
                    activity.info("요인별 판단의 상충관계와 상환능력 영향을 종합하고 있습니다.")
                    h.synthesize()
                    if live:
                        write_section()
                except Exception as error:
                    h.store.event(action="synthesis", status="ERROR", error=str(error))
                    st.session_state.generation_message = "종합의견 작성이 중단되었습니다. 작성된 보고서 본문은 보존했습니다."
            else:
                st.session_state.generation_message = "보고서 생성이 완료되지 않았습니다. 연결 및 실행 오류를 확인해야 합니다."
        progress.empty()
        activity.empty()
    except Exception as error:
        if h:
            h.store.event(action="report_generation", status="ERROR", error=str(error))
        if not locals().get("client") or "LLM" in str(error) or "model" in str(error).lower():
            st.session_state.generation_message = "LLM 서버에 연결되지 않아 보고서를 작성하지 못했습니다. Colab 서버 연결이 필요합니다."
        else:
            st.session_state.generation_message = "보고서 작성을 시작하지 못했습니다. 자료 또는 서버 연결을 확인해야 합니다."
    st.rerun()

if h and report_document(h)["sections"]:
    st.download_button("심사보고서 다운로드", report_markdown(report_document(h)), "credit_review_report.md", mime="text/markdown")
