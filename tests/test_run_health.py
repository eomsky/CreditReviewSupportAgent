import json
from datetime import date
import httpx
from streamlit.testing.v1 import AppTest
from test_ui import APP
from credit_review.harness import Harness
from credit_review.demo import DemoClient, demo_sources
from credit_review.run_health import saved_status, status_message, explain_failure


def test_530_records_each_one_pass_section_and_persists_reason(tmp_path, monkeypatch):
    monkeypatch.setenv('CREDIT_WORKSPACE', str(tmp_path))
    monkeypatch.setenv('LLM_BASE_URL', 'https://example.test/v1')
    monkeypatch.setenv('LLM_MODEL', 'test')
    h = Harness.create(tmp_path, 'outage', date(2026,4,7), demo_sources(), DemoClient(), 'LIVE')
    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith('/models'):
            return httpx.Response(200, json={'data':[{'id':'test'}]})
        return httpx.Response(530, text='tunnel unavailable')
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    app = AppTest.from_file(APP).run(timeout=30)
    next(b for b in app.button if b.label == '보고서 작성 계속').click().run(timeout=30)
    assert not app.exception
    # The fixed contract is one attempt for each of seven sections, without retry.
    assert calls.count('/v1/chat/completions') == 7
    assert len(list(h.store.path.glob('section_*_attempt.json'))) == 7
    outcome = saved_status(h)
    assert outcome['status'] == 'FAILED'
    assert '530' in outcome['reason']
    assert outcome['question']
    assert any('530' in x.value and '검토 질문' in x.value for x in app.warning)
    state = json.loads((h.store.path/'state.json').read_text())
    assert state['factors']['F02']['steps'] == 0
    # New browser session still shows the recorded cause.
    fresh = AppTest.from_file(APP).run(timeout=30)
    assert any('530' in x.value for x in fresh.warning)


def test_failure_message_does_not_leak_connection_secrets():
    reason = explain_failure('HTTPStatusError: 530 https://secret.test/token?api_key=SECRET')
    assert '530' in reason and 'SECRET' not in reason and 'secret.test' not in reason
