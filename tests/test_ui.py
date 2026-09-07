from streamlit.testing.v1 import AppTest
from pathlib import Path

def test_workbench_initial_render():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app' / 'workbench.py')).run(timeout=30)
    assert not app.exception
    assert '기업여신' in app.title[0].value

def test_saved_results_visible_without_debug(tmp_path, monkeypatch):
    from datetime import date
    from credit_review.harness import Harness
    from credit_review.demo import DemoClient, demo_sources
    from credit_review.models import Judgement
    monkeypatch.setenv('CREDIT_WORKSPACE', str(tmp_path))
    h = Harness.create(tmp_path, 'result_case', date(2026,4,7), demo_sources(), DemoClient(), 'DEMO')
    h.state.factors['F24'].judgement = Judgement(summary='보유현금 부족을 추가 확인해야 합니다.', evidence_ids=['demo_cash'])
    h.save()
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app' / 'workbench.py')).run(timeout=30)
    assert not app.exception
    assert any('보유현금 부족' in x.value for x in app.markdown)
    assert not app.json
    assert not app.code
    assert not any(b.label == '다음 단계 실행' for b in app.button)
    next(c for c in app.checkbox if c.label == '상세 실행 정보 보기').check().run()
    assert not app.exception
    assert app.json
