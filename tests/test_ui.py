from pathlib import Path
from datetime import date
from streamlit.testing.v1 import AppTest
from credit_review.demo import DemoClient, demo_sources
from credit_review.harness import Harness
from credit_review.models import Judgement
from credit_review.reporting import report_document, report_markdown

APP = str(Path(__file__).resolve().parents[1] / 'app' / 'workbench.py')

def test_workbench_initial_render(tmp_path, monkeypatch):
    monkeypatch.setenv('CREDIT_WORKSPACE', str(tmp_path))
    app = AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    assert any('종합심사의견' in x.value for x in app.title)
    assert not app.json
    assert not app.checkbox

def test_report_hides_diagnostics_and_retains_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv('CREDIT_WORKSPACE', str(tmp_path))
    h = Harness.create(tmp_path, 'report_case', date(2026,4,7), demo_sources(), DemoClient(), 'DEMO')
    h.state.factors['F24'].judgement = Judgement(summary='차입 만기에 비해 보유현금이 부족합니다.',
        evidence_ids=['demo_cash'], risks=['유동성 부담'], missing=['INTERNAL_MISSING_ONLY'], conflicts=['INTERNAL_CONFLICT_ONLY'])
    h.save()
    text = report_markdown(report_document(h))
    assert '차입구조 및 상환능력' in text
    assert '보유현금이 부족' in text
    assert '유동성 부담' in text
    assert 'INTERNAL_' not in text
    assert '미분석' not in text
    app = AppTest.from_file(APP).run(timeout=30)
    assert not app.exception
    assert any('보유현금이 부족' in x.value for x in app.markdown)
    assert not app.json and not app.code and not app.checkbox
    assert not any('추가 확인' in x.label for x in app.expander)
    assert h.state.factors['F24'].judgement.missing == ['INTERNAL_MISSING_ONLY']

def test_missing_llm_preflight_preserves_report(tmp_path, monkeypatch):
    monkeypatch.setenv('CREDIT_WORKSPACE', str(tmp_path))
    monkeypatch.delenv('LLM_BASE_URL', raising=False)
    monkeypatch.delenv('LLM_MODEL', raising=False)
    h = Harness.create(tmp_path, 'live_case', date(2026,4,7), demo_sources(), DemoClient(), 'LIVE')
    h.state.factors['F24'].judgement = Judgement(summary='보존할 기존 분석', evidence_ids=['demo_cash'])
    h.save()
    app = AppTest.from_file(APP).run(timeout=30)
    next(b for b in app.button if b.label == '보고서 작성 계속').click().run(timeout=30)
    assert not app.exception
    assert any('LLM 서버' in x.value for x in app.error)
    assert any('보존할 기존 분석' in x.value for x in app.markdown)
    assert len(list(tmp_path.glob('cases/*/runs/*/state.json'))) == 1


def test_live_benchmark_view_reads_saved_opinions_without_running_analysis(tmp_path, monkeypatch):
    monkeypatch.setenv('CREDIT_WORKSPACE', str(tmp_path))
    from credit_review.models import Judgement
    h = Harness.create(tmp_path/'benchmarks', 'full', date(2026,4,7), demo_sources(), DemoClient(), 'DEMO')
    h.state.factors['F24'].judgement = Judgement(summary='실시간 표시할 상환능력 의견', evidence_ids=['demo_cash'])
    h.save()
    before = {p:p.stat().st_mtime_ns for p in h.store.path.rglob('*') if p.is_file()}
    app = AppTest.from_file(APP)
    app.query_params['benchmark'] = 'latest'
    app.run(timeout=30)
    assert not app.exception
    assert any('실시간 표시할 상환능력 의견' in x.value for x in app.markdown)
    assert not app.button and not app.code and not app.json
    assert before == {p:p.stat().st_mtime_ns for p in h.store.path.rglob('*') if p.is_file()}
