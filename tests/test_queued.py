import json
import time
from threading import Event, Lock
import pytest
from test_harness import make
from credit_review.grouped import analyse_grouped
from credit_review.queued import eligible
from credit_review.parallel import Measurements, MeasuredClient


def reply(ids):
    return json.dumps({'actions':[{'factor_id':fid,'action':{'action':'conclude',
        'reason':'supported limitations','judgement':{'summary':'Limited evidence',
        'evidence_ids':[],'missing':['unavailable sources']}}} for fid in ids]})


def test_two_service_slots_and_completion_order(tmp_path):
    h = make(tmp_path)
    second_started = Event()
    lock = Lock()
    counts = {'active':0,'maximum':0}
    class Client:
        def next_actions(self, context):
            ids=list(context['factors'])
            with lock:
                counts['active']+=1
                counts['maximum']=max(counts['maximum'],counts['active'])
            if 'F01' in ids:
                assert second_started.wait(1)
                time.sleep(.06)
            else:
                second_started.set()
            with lock:
                counts['active']-=1
            return reply(ids)
    metrics = Measurements()
    h.client=MeasuredClient(Client(),metrics)
    events=list(analyse_grouped(h,['F01','F02','F04','F05'],concurrency=2,batch_size=2,metrics=metrics))
    assert counts['maximum']==2
    finished=[e['factor_id'] for e in events if e['kind']=='state' and e['value'].judgement]
    assert finished[:2]==['F04','F05']
    assert metrics.snapshot()['llm_calls']==2
    assert metrics.snapshot()['llm_inflight']==0


def test_dependent_and_shared_financial_work_waits(tmp_path):
    h=make(tmp_path)
    assert not eligible('F14', {'F13'}, h.state.factors, ['F13','F14'])
    assert eligible('F07', {'F13'}, h.state.factors, ['F13','F07'])
    assert not eligible('F24', set(), h.state.factors, ['F13','F24'])
    assert not eligible('F30', set(), h.state.factors, ['F01','F30'])


def test_expired_parallel_replies_cannot_mutate_saved_state(tmp_path):
    h=make(tmp_path)
    class Client:
        def next_actions(self, context):
            time.sleep(.1)
            return reply(context['factors'])
    h.client=Client()
    with pytest.raises(RuntimeError,match='한도'):
        list(analyse_grouped(h,['F01','F02'],concurrency=2,batch_size=1,time_budget=.03))
    time.sleep(.12)
    assert not any(f.judgement for f in h.state.factors.values())


def test_occupancy_is_union_not_sum_of_overlapping_requests():
    m=Measurements()
    a=m.begin('llm_one')
    b=m.begin('llm_two')
    time.sleep(.01)
    live=m.snapshot()
    assert live['llm_inflight']==2
    assert live['mean_requests_inflight']>live['request_busy_fraction']
    assert 0<=live['request_busy_fraction']<=1
    m.finish(a)
    m.finish(b)
    assert m.snapshot()['llm_calls']==2


def test_local_processing_overlaps_independent_llm_request(tmp_path, monkeypatch):
    import credit_review.grouped as grouped
    h = make(tmp_path)
    other_started, local_finished = Event(), Event()
    original = grouped.apply_group_independently
    class Client:
        def next_actions(self, context):
            ids = list(context['factors'])
            if ids == ['F01']:
                assert other_started.wait(1)
            else:
                other_started.set()
                assert local_finished.wait(1)
            return reply(ids)
    def apply(worker, ids, raw, response):
        if ids == ['F01']:
            assert other_started.is_set()
            time.sleep(.01)  # Simulated local tool work, not a CPU throughput test.
            original(worker, ids, raw, response)
            local_finished.set()
        else:
            original(worker, ids, raw, response)
    monkeypatch.setattr(grouped, 'apply_group_independently', apply)
    metrics = Measurements()
    h.client = MeasuredClient(Client(), metrics)
    list(analyse_grouped(h, ['F01','F02'], concurrency=2, batch_size=1, metrics=metrics))
    assert metrics.snapshot()['local_apply_during_request_seconds'] >= .01


def test_server_token_usage_is_retained_by_measured_client():
    class Client:
        def set_usage_observer(self, observer):
            self.observer = observer
        def next_actions(self, context):
            self.observer({'prompt_tokens':100, 'completion_tokens':20, 'total_tokens':120})
            return '{}'
    metrics = Measurements()
    MeasuredClient(Client(), metrics).next_actions({})
    usage = metrics.snapshot()['token_usage']
    assert len(usage) == 1
    assert {k:usage[0][k] for k in ('prompt_tokens','completion_tokens','total_tokens')} == {
        'prompt_tokens':100, 'completion_tokens':20, 'total_tokens':120}
    assert usage[0]['kind'] == 'llm_next_actions'
    assert usage[0]['call_id'] == metrics.snapshot()['operations'][0]['call_id']
