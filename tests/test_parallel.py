import json
from threading import Barrier, Lock
from datetime import date
import pytest
from credit_review.harness import Harness
from credit_review.demo import DemoClient, demo_sources
from credit_review.models import Action
from credit_review.parallel import analyse_factors, run_lease, CachedTools, Measurements, MeasuredClient
from test_harness import make


def test_two_workers_merge_without_losing_state_and_resume_skips(tmp_path):
    barrier, lock = Barrier(2), Lock()
    class Client:
        active = 0
        peak = 0
        calls = 0
        def next_action(self, context):
            with lock:
                self.active += 1
                self.peak = max(self.peak, self.active)
                self.calls += 1
            barrier.wait(timeout=5)
            with lock:
                self.active -= 1
            return json.dumps({'action':'conclude', 'reason':'supported qualification',
                'judgement':{'summary':context['factor']['name'], 'evidence_ids':[], 'missing':['not available']}})
    client = Client()
    h = Harness.create(tmp_path, 'parallel', date(2026,4,7), demo_sources(), client)
    metrics = Measurements()
    h.client = MeasuredClient(client, metrics)
    with run_lease(h):
        events = list(analyse_factors(h, ['F02','F03'], metrics=metrics))
    assert client.peak == 2
    state = json.loads((h.store.path/'state.json').read_text(encoding='utf-8'))
    assert all(state['factors'][fid]['judgement'] for fid in ['F02','F03'])
    assert metrics.snapshot()['llm_calls'] == 2
    assert metrics.first_report_seconds is not None
    list(analyse_factors(h, ['F02','F03']))
    assert client.calls == 2
    assert not list(h.store.path.glob('*.lock'))
    assert sum(e['kind']=='done' for e in events) == 2


def test_run_lease_rejects_second_writer_without_removing_first(tmp_path):
    h = make(tmp_path)
    with run_lease(h):
        with pytest.raises(RuntimeError, match='active writer'):
            with run_lease(h):
                pass
        assert (h.store.path/'.run.lock').exists()
    assert not (h.store.path/'.run.lock').exists()


def test_reuse_validated_dataset_preserves_provenance_and_rejects_foreign_id(tmp_path):
    h = make(tmp_path)
    for _ in range(2):
        h.step('F24')
    aid = h.state.factors['F24'].dataset_ids[0]
    h.apply('F16', Action(action='reuse', reason='same scope', reuse_dataset_ids=[aid]), 'test')
    assert aid in h.state.factors['F16'].dataset_ids
    assert h.state.factors['F16'].evidence_ids
    with pytest.raises(ValueError, match='source revision'):
        h.apply('F16', Action(action='reuse', reason='invalid', reuse_dataset_ids=['dataset_other']), 'test')


def test_exact_cache_does_not_reuse_changed_query_or_return_mutable_result(tmp_path):
    h = make(tmp_path)
    metrics = Measurements()
    cache = CachedTools(h.retriever, h.executor, metrics)
    first = cache.search('현금흐름')
    first.clear()
    assert cache.search('현금흐름')
    cache.search('차입금')
    assert metrics.snapshot()['cache_hits'] == 1

def test_service_failure_drains_other_worker_and_never_starts_next(tmp_path):
    from threading import Event
    entered, failed = Event(), Event()
    class Client:
        calls = []
        def next_action(self, context):
            fid = context['state']['factor_id']
            self.calls.append(fid)
            if fid == 'F02':
                assert entered.wait(5)
                failed.set()
                raise RuntimeError('HTTPStatusError: 530')
            if fid == 'F03':
                entered.set()
                assert failed.wait(5)
                return json.dumps({'action':'conclude','reason':'qualified',
                    'judgement':{'summary':'preserved', 'evidence_ids':[], 'missing':['unknown']}})
            raise AssertionError('No new factor may start after failure')
    client = Client()
    h = Harness.create(tmp_path, 'failure', date(2026,4,7), demo_sources(), client)
    with run_lease(h), pytest.raises(RuntimeError, match='530'):
        list(analyse_factors(h, ['F02','F03','F04']))
    assert client.calls == ['F02','F03']
    assert h.state.factors['F03'].judgement.summary == 'preserved'
    assert h.state.factors['F04'].steps == 0

def test_existing_inquiry_cannot_request_another_plan(tmp_path, monkeypatch):
    from credit_review.llm import ColabClient
    from credit_review.models import Inquiry
    h = make(tmp_path)
    f = h.state.factors['F24']
    f.inquiry = Inquiry(question='상환능력?', hypotheses=['충분'], evidence_tests=['현금 확인'], change_reason='최초')
    context = h.context('F24')
    assert 'plan' not in context['available_actions']
    client = object.__new__(ColabClient)
    received = {}
    def complete(system, context, schema):
        received.update(schema)
        return '{}'
    monkeypatch.setattr(client, 'complete', complete)
    client.next_action(context)
    assert 'plan' not in received['properties']['action']['enum']
    assert 'reframe' in received['properties']['action']['enum']
