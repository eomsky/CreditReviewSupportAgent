import json
import pytest
from test_harness import make
from credit_review.models import Action
from credit_review.llm import report_deltas


def test_usage_only_sse_event_is_recorded_without_report_text():
    usage=[]
    lines=['data: '+json.dumps({'choices':[{'delta':{'content':'본문'},'finish_reason':None}]}),
           'data: '+json.dumps({'choices':[{'delta':{},'finish_reason':'stop'}]}),
           'data: '+json.dumps({'choices':[],'usage':{'completion_tokens':2,'prompt_tokens':10}}),
           'data: [DONE]']
    assert ''.join(report_deltas(lines,usage.append))=='본문'
    assert usage==[{'completion_tokens':2,'prompt_tokens':10}]


def inquiry(question="Can cash cover maturities?"):
    return dict(question=question, hypotheses=["Cash is insufficient"],
                evidence_tests=["Compare cash with debt maturities"], change_reason="Test repayment ability")


def test_reframe_preserves_assets_and_bounds_iterations(tmp_path):
    h = make(tmp_path)
    h.step('F24')
    h.step('F24')
    f = h.state.factors['F24']
    before = (list(f.evidence_ids), list(f.dataset_ids))
    for n in range(3):
        h.apply('F24', Action(action='reframe', reason='new evidence', inquiry=inquiry(str(n))), 'test')
    assert (f.evidence_ids, f.dataset_ids) == before
    assert f.inquiry.question == '2'
    with pytest.raises(ValueError, match='limit'):
        h.apply('F24', Action(action='reframe', reason='loop', inquiry=inquiry()), 'test')


def test_invalid_action_is_returned_as_feedback_with_bounded_retries(tmp_path):
    h = make(tmp_path)
    h.client.next_action = lambda ctx: 'bad json'
    h.step('F24', repair_attempts=2)
    assert h.context('F24')['state']['failed_response'] == 'bad json'
    assert h.state.factors['F24'].status == 'RETRYING'
    h.step('F24', repair_attempts=2)
    h.step('F24', repair_attempts=2)
    assert h.state.factors['F24'].status == 'ERROR'
    assert h.state.factors['F24'].steps == 3


def test_sse_content_only_and_interruption_detection():
    def event(delta, finish=None):
        return 'data: ' + json.dumps({'choices':[{'delta':delta,'finish_reason':finish}]})
    lines = [event({'reasoning_content':'private'}), event({'content':'보고서'}), event({}, 'stop'), 'data: [DONE]']
    assert ''.join(report_deltas(lines)) == '보고서'
    with pytest.raises(ValueError, match='disconnected'):
        list(report_deltas([event({'content':'partial'})]))
    with pytest.raises(ValueError, match='truncated'):
        list(report_deltas([event({}, 'length')]))


def test_stream_failure_preserves_saved_report_and_partial_artifact(tmp_path):
    h = make(tmp_path)
    for _ in range(4):
        h.step('F24')
    h.state.factors['F24'].report_text = 'previous report'
    def broken(context):
        yield 'new partial'
        raise ValueError('disconnected')
    h.client.stream_report = broken
    with pytest.raises(ValueError):
        list(h.stream_narrative('F24'))
    assert h.state.factors['F24'].report_text == 'previous report'
    assert any(a['stage'] == 'narrative_partial' for a in h.store.artifacts())
    h.client.stream_report = lambda ctx: iter(['complete ', 'report'])
    assert ''.join(h.stream_narrative('F24')) == 'complete report'
    assert h.state.factors['F24'].report_text == 'complete report'
