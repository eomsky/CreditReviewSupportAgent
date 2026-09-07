"""Results-first view over the same persisted harness artifacts."""
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from credit_review.demo import DemoClient, demo_sources
from credit_review.documents import from_json, from_pdf
from credit_review.harness import Harness
from credit_review.llm import ColabClient
from credit_review.registry import FACTORS
from credit_review.store import json_text, identifier

ROOT = Path(os.environ.get("CREDIT_WORKSPACE", "workspace"))

class LazyLiveClient:
    # Viewing saved results never requires an available LLM server.
    model = os.environ.get("LLM_MODEL", "")
    def next_action(self, context):
        return ColabClient().next_action(context)
    def synthesize(self, context):
        return ColabClient().synthesize(context)

def load_result(path):
    meta = json.loads(path.read_text(encoding="utf-8"))
    client = DemoClient() if meta["mode"] == "DEMO" else LazyLiveClient()
    return Harness.resume(ROOT, meta["case_id"], meta["run_id"], client)

def show_results(h):
    if h.state.mode == "DEMO":
        st.caption("가상 자료 예시입니다. 실제 기업 분석 결과가 아닙니다.")
    completed = {fid: f for fid, f in h.state.factors.items() if f.judgement}
    st.caption(f"{h.state.case_id} · 기준일 {h.state.review_date} · 분석 의견 {len(completed)}/30개 · 검토용 초안")
    st.subheader("종합 분석")
    if h.state.report_id:
        report = h.store.get(h.state.report_id)["payload"]
        for p in report["paragraphs"]:
            st.write(p["text"])
        for limitation in report.get("limitations", []):
            st.caption(limitation)
    elif completed:
        for fid, f in completed.items():
            st.markdown(f"**{FACTORS[fid]['name']}**")
            st.write(f.judgement.summary)
        st.caption("확보된 요인별 의견입니다. 종합 분석은 결과가 추가되는 대로 갱신됩니다.")
    else:
        st.info("아직 분석 의견이 없습니다. 자료를 추가하고 분석 시작을 누르면 이곳에 결과가 쌓입니다.")
    missing = [f"{FACTORS[fid]['name']}: {', '.join(f.judgement.missing)}"
               for fid, f in completed.items() if f.judgement.missing]
    conflicts = [f"{FACTORS[fid]['name']}: {', '.join(f.judgement.conflicts)}"
                 for fid, f in completed.items() if f.judgement.conflicts]
    pending = [FACTORS[fid]["name"] for fid, f in h.state.factors.items() if not f.judgement]
    with st.expander(f"추가 확인 필요 · 미분석 {len(pending)}개"):
        for item in missing + conflicts:
            st.write(item)
        if pending:
            st.write("아직 의견이 없는 항목: " + ", ".join(pending))
        if any(f.error for f in h.state.factors.values()):
            st.write("일부 분석을 완료하지 못했습니다. 확보된 결과는 유지됩니다.")

st.set_page_config(page_title="기업여신 심사 결과", layout="wide")
st.title("기업여신 심사 결과")
saved = sorted(ROOT.glob("cases/*/runs/*/state.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True)
if "harness" not in st.session_state and saved:
    try:
        st.session_state.harness = load_result(saved[0])
    except Exception as error:
        st.warning("저장된 결과를 열지 못했습니다. 다른 결과를 선택하거나 자료를 등록하세요.")
        st.session_state.load_error = str(error)

with st.sidebar:
    st.subheader("심사 자료")
    if saved:
        selected = st.selectbox("저장된 결과", saved, format_func=lambda p: f"{p.parents[2].name} · {p.parent.name[-8:]}")
        if st.button("결과 열기"):
            st.session_state.harness = load_result(selected)
            st.rerun()
    upload = st.file_uploader("자료 추가", type=["json", "pdf"], accept_multiple_files=True)
    case_id = st.text_input("심사건 이름", "case_001")
    cutoff = st.date_input("심사 기준일", date(2026, 4, 7))
    published = st.date_input("자료 공표일", date(2026, 3, 31))
    start_new = st.button("자료로 분석 시작", type="primary", disabled=not upload)
    with st.expander("설정"):
        embedding = st.text_input("임베딩 모델", os.environ.get("EMBEDDING_MODEL", ""))
        demo = st.button("가상 자료 예시 보기")
        st.caption("PDF 기본 추출은 OCR·연속표 통합을 보장하지 않습니다.")
    technical = st.checkbox("상세 실행 정보 보기", value=False)

run_requested = False
if start_new or demo:
    try:
        identifier(case_id)
        sources = demo_sources() if demo else []
        for file in ([] if demo else upload):
            if file.name.lower().endswith(".json"):
                sources.extend(from_json(file.getvalue()))
            else:
                import hashlib
                folder = ROOT / "cases" / case_id / "sources"
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / (hashlib.sha256(file.getvalue()).hexdigest() + ".pdf")
                path.write_bytes(file.getvalue())
                sources.extend(from_pdf(path, published))
        if len({s.id for s in sources}) != len(sources):
            raise ValueError("중복 자료가 있습니다")
        st.session_state.harness = Harness.create(ROOT, "demo_case" if demo else case_id,
            cutoff, sources, DemoClient() if demo else LazyLiveClient(), "DEMO" if demo else "LIVE", embedding)
        run_requested = True
    except Exception as error:
        st.error(str(error))

h = st.session_state.get("harness")
if not h:
    st.info("자료를 추가하면 분석 의견과 핵심 수치가 이곳에 표시됩니다.")
    st.stop()

result_area = st.empty()
with result_area.container():
    show_results(h)
run_requested = st.button("분석 결과 갱신") or run_requested
if run_requested:
    targets = ["F24"] if h.state.mode == "DEMO" else list(FACTORS)
    h.state.report_id = None
    h.save()
    progress = st.empty()
    for fid in targets:
        f = h.state.factors[fid]
        if f.judgement:
            continue
        if f.status in ("ERROR", "LIMIT_REACHED", "NO_PROGRESS"):
            h.reset_factor(fid)
        for _ in range(15):
            progress.info(f"{FACTORS[fid]['name']} 분석 중 · 현재 결과는 아래에서 확인할 수 있습니다.")
            f = h.step(fid)
            with result_area.container():
                show_results(h)
            if f.judgement or f.status in ("ERROR", "LIMIT_REACHED", "NO_PROGRESS"):
                break
        if f.error:
            progress.warning("분석 연결을 확인해야 합니다. 확보된 결과를 먼저 표시합니다.")
            break
    if any(f.judgement for f in h.state.factors.values()):
        try:
            h.synthesize()
        except Exception as error:
            h.store.event(action="synthesis", status="ERROR", error=str(error))
            st.session_state.synthesis_error = str(error)
    progress.empty()
    st.rerun()

available = [fid for fid, f in h.state.factors.items() if f.judgement or f.dataset_ids or f.calculation_ids]
choices = available + [fid for fid in FACTORS if fid not in available]
fid = st.selectbox("항목별 결과", choices, format_func=lambda k: FACTORS[k]["name"])
f = h.state.factors[fid]
st.subheader(FACTORS[fid]["name"])
if f.judgement:
    st.write(f.judgement.summary)
    for label, values in [("주요 위험", f.judgement.risks), ("완화요인", f.judgement.mitigants), ("추가 확인", f.judgement.missing), ("상충하는 근거", f.judgement.conflicts)]:
        if values:
            st.markdown(f"**{label}**")
            for value in values:
                st.write("• " + value)
else:
    st.caption("추가 확인 필요 · 아직 분석 의견이 없습니다.")
for aid in f.dataset_ids:
    data = h.store.get(aid)["payload"]
    st.write(data["description"])
    frame = pd.DataFrame(data["rows"])
    frame.columns = [c["name"] + (f" ({c['unit']})" if c.get("unit") else "") for c in data["columns"]]
    st.dataframe(frame, hide_index=True, use_container_width=True)
for aid in f.calculation_ids:
    output = h.store.get(aid)["payload"]
    st.markdown("**" + output["plan"]["purpose"] + "**")
    value = output.get("result")
    if isinstance(value, dict):
        st.dataframe([{"항목": k, "결과": json_text(v) if isinstance(v, (dict, list)) else str(v)} for k, v in value.items()], hide_index=True, use_container_width=True)
    else:
        st.write(value)
    for assumption in output["plan"].get("assumptions", []):
        st.caption(assumption)
with st.expander("근거 자료 보기"):
    for row in h.retriever.read(f.evidence_ids):
        st.caption(f"{row['document_id']} · {row['page']}쪽")
        st.text(row["text"])

if h.state.report_id:
    report = h.store.get(h.state.report_id)["payload"]
    markdown = "# " + report["title"] + "\n\n검토용 초안\n\n" + "\n\n".join(p["text"] for p in report["paragraphs"])
    markdown += "\n\n추가 확인: " + ", ".join(FACTORS[x]["name"] for x in report["unanalysed"])
    st.download_button("보고서 다운로드", markdown, "review_draft.md")

if technical:
    st.divider()
    st.subheader("상세 실행 정보")
    st.caption(f"실행 {h.state.run_id} · 검색 {h.retriever.mode}")
    st.json(f.model_dump(mode="json"))
    if st.button("선택 항목 다시 분석"):
        h.reset_factor(fid)
        st.rerun()
    if st.button("선택 항목 한 단계 실행"):
        h.step(fid)
        st.rerun()
    artifacts = h.store.artifacts()
    if artifacts:
        aid = st.selectbox("입력·출력 기록", [a["id"] for a in artifacts])
        st.json(h.store.get(aid))
        st.download_button("JSON 다운로드", json_text(h.store.get(aid)), f"{aid}.json")
    for aid in f.calculation_ids:
        st.code(h.store.get(aid)["payload"]["plan"]["code"], language="python")
    events = h.store.path / "events.jsonl"
    if events.exists():
        st.text(events.read_text(encoding="utf-8"))
