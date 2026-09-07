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

st.set_page_config(page_title="Credit review harness", layout="wide")
st.title("기업여신 심사 테스트 하네스")
st.caption("30개 요인 · 단계별 JSON · 근거 표 · Python 계산 · 검토용 종합 초안")
ROOT = Path("workspace")

with st.sidebar:
    mode = st.radio("실행 모드", ["DEMO", "LIVE"])
    st.caption("DEMO: 가상 자료와 사전 정의 JSON. LIVE: Colab LLM API 호출.")
    case_id = st.text_input("심사건 ID", "demo_case" if mode == "DEMO" else "case_001")
    cutoff = st.date_input("심사 기준일 / 미래자료 차단", date(2026, 4, 7))
    published = st.date_input("PDF 공표일 (직접 확인)", date(2026, 3, 31))
    upload = st.file_uploader("자료 추가 (새 실행 생성)", type=["json", "pdf"], accept_multiple_files=True)
    st.caption("구조화 JSON 권장. PDF 기본 파서는 OCR·연속표 통합 미지원.")
    embedding = st.text_input("CPU 임베딩 모델 (선택)", os.environ.get("EMBEDDING_MODEL", ""))
    if st.button("새 실행 만들기"):
        try:
            identifier(case_id)
            client = DemoClient() if mode == "DEMO" else ColabClient()
            sources = demo_sources() if mode == "DEMO" else []
            for file in upload:
                if file.name.lower().endswith(".json"):
                    sources.extend(from_json(file.getvalue()))
                else:
                    import hashlib
                    folder = ROOT / "cases" / case_id / "sources"
                    folder.mkdir(parents=True, exist_ok=True)
                    path = folder / (hashlib.sha256(file.getvalue()).hexdigest() + ".pdf")
                    path.write_bytes(file.getvalue())
                    sources.extend(from_pdf(path, published))
            if not sources:
                raise ValueError("자료를 추가하세요")
            ids = [s.id for s in sources]
            if len(ids) != len(set(ids)):
                raise ValueError("중복 문서/근거 ID가 있습니다")
            st.session_state.harness = Harness.create(ROOT, case_id, cutoff, sources, client, mode, embedding)
            st.session_state.search_hits = []
        except Exception as error:
            st.error(str(error))
    saved = sorted(ROOT.glob("cases/*/runs/*/state.json"))
    selected = st.selectbox("저장된 실행", saved, format_func=lambda p: f"{p.parents[2].name}/{p.parent.name}") if saved else None
    if selected and st.button("실행 재개"):
        try:
            meta = json.loads(selected.read_text(encoding="utf-8"))
            client = DemoClient() if meta["mode"] == "DEMO" else ColabClient()
            st.session_state.harness = Harness.resume(ROOT, meta["case_id"], meta["run_id"], client)
            st.session_state.search_hits = []
        except Exception as error:
            st.error(str(error))

h = st.session_state.get("harness")
if not h:
    st.info("왼쪽에서 새 실행을 만드세요. 데모는 F24 상환능력을 4단계로 실행합니다.")
    st.code("docker build -f docker/calculator.Dockerfile -t credit-review-calculator:0.1 .\npython -m streamlit run app/workbench.py")
    st.stop()

st.write(f"심사건: {h.state.case_id} / 실행: {h.state.run_id} / 모드: {h.state.mode}")
st.caption(f"검색: {h.retriever.mode} | 생성 상태: {h.state.generation_status} | 계산/판단의 의미 검증은 검토 대기")
if h.state.mode == "DEMO":
    st.warning("가상 자료 · 사전 정의된 JSON 데모입니다. 실제 LLM 분석 또는 실제 기업 평가가 아닙니다.")
table = [{"ID": fid, "요인": FACTORS[fid]["name"], "상태": f.status,
          "근거요건 충족": f"{len(f.requirements_met)}/{len(FACTORS[fid]['required_evidence'])}",
          "단계": f.steps, "오류": f.error or ""} for fid, f in h.state.factors.items()]
st.dataframe(table, hide_index=True, use_container_width=True)
fid = st.selectbox("분석 요인", list(FACTORS), index=23, format_func=lambda k: f"{k} {FACTORS[k]['name']}")
left, middle, right = st.columns(3)
if left.button("다음 단계 실행"):
    with st.spinner("LLM / 검색 / Python 단계 실행 중"):
        h.step(fid)
    st.rerun()
if middle.button("요인 분석 재시작 (기록 보존)"):
    h.reset_factor(fid)
    st.rerun()
if right.button("분석된 요인으로 종합 초안 작성"):
    try:
        with st.spinner("종합 분석 중"):
            h.synthesize()
        st.rerun()
    except Exception as error:
        st.error(str(error))

tabs = st.tabs(["요인 분석", "데이터·계산", "근거 검색", "실행 JSON", "보고서"])
f = h.state.factors[fid]
with tabs[0]:
    if f.error:
        st.error(f.error)
    st.json(f.model_dump(mode="json"))
with tabs[1]:
    for aid in f.dataset_ids:
        data = h.store.get(aid)["payload"]
        st.write(aid, data["description"])
        st.dataframe(pd.DataFrame(data["rows"]), hide_index=True)
        with st.expander("스키마·단위·셀 출처"):
            st.json(data)
    for aid in f.calculation_ids:
        result = h.store.get(aid)["payload"]
        st.code(result["plan"]["code"], language="python")
        st.json(result)
with tabs[2]:
    query = st.text_input("같은 자료 재검색", "상환 현금흐름")
    if st.button("검색"):
        hits = h.retriever.search(query)
        h.store.put("manual_search", {"query": query, "hits": hits})
        st.session_state.search_hits = hits
    for hit in st.session_state.get("search_hits", []):
        st.json(hit)
    for row in h.retriever.read(f.evidence_ids):
        with st.expander(f"{row['id']} · p.{row['page']} · {row['kind']}"):
            st.text(row["text"])
with tabs[3]:
    artifacts = h.store.artifacts()
    if artifacts:
        aid = st.selectbox("산출물", [a["id"] for a in artifacts])
        artifact = h.store.get(aid)
        st.json(artifact)
        st.download_button("JSON 다운로드", json_text(artifact), f"{aid}.json", mime="application/json")
    events = h.store.path / "events.jsonl"
    if events.exists():
        st.text(events.read_text(encoding="utf-8"))
with tabs[4]:
    if h.state.report_id:
        report = h.store.get(h.state.report_id)["payload"]
        st.warning("검토용 초안. 미분석 요인 및 수치·의미 검증 상태를 확인하세요.")
        st.subheader(report["title"])
        for p in report["paragraphs"]:
            st.write(p["text"])
            st.caption("근거: " + ", ".join(p.get("evidence_ids", [])))
        st.json(report)
        markdown = "# " + report["title"] + "\n\n검토용 초안\n\n" + "\n\n".join(p["text"] for p in report["paragraphs"])
        markdown += "\n\n미분석 요인: " + ", ".join(report["unanalysed"])
        st.download_button("초안 Markdown", markdown, "review_draft.md")
    else:
        st.info("요인별 분석 후 종합 초안을 생성하세요.")
