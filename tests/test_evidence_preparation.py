import json
from datetime import date
from credit_review.harness import Harness
from credit_review.models import Source
from credit_review.grouped import group_context, shared_context, analyse_grouped
from credit_review.shared_work import SharedWork
from test_harness import make
from test_table_access import source


def test_prior_lookup_does_not_replace_factor_specific_window(tmp_path):
    sources = [Source(id=sid, document_id='doc', page=i, published_at=date(2026,3,31), text=text)
        for i, (sid,text) in enumerate([('product','product evidence'),('owner','ownership evidence')],1)]
    h = Harness.create(tmp_path, 'test', date(2026,4,7), sources, None)
    h.state.factors['F07'].recent_source_ids = ['product']
    memory = SharedWork(h)
    memory.search = lambda *a, **k: [{'evidence_ids':['owner'],'summary':'Prior candidate'}]
    context = shared_context(h, ['F07'], memory)
    assert h.state.factors['F07'].recent_source_ids == ['product']
    assert list(context['sources']) == ['product']
    assert context['prior_work']['F07'][0]['evidence_ids'] == ['owner']


def test_read_restores_paragraph_tail_without_changing_original(tmp_path):
    from credit_review.models import Action
    text = 'context ' * 1000 + 'material qualification at end'
    h = Harness.create(tmp_path, 'test', date(2026,4,7), [Source(id='p',document_id='doc',
        page=1,published_at=date(2026,3,31),text=text)], None)
    h.state.factors['F02'].recent_source_ids = ['p']
    assert group_context(h, ['F02'])['sources']['p']['excerpt_only']
    h.apply('F02', Action(action='read', reason='qualification', source_ids=['p']), 'test')
    actual = group_context(h, ['F02'])['sources']['p']
    assert actual['text'] == text and actual['read_complete']
    assert 'excerpt_only' not in actual


def test_numeric_factor_preloads_only_matched_table(tmp_path):
    table = source()
    table.metadata['structured']['elements'][0]['title'] = '연결 재무상태표 부채총계 자본총계'
    h = Harness.create(tmp_path, 'test', date(2026,4,7), [table], None)
    h.prepare_evidence('F16')
    assert h.state.factors['F16'].read_source_ids == ['table1']
    assert h.context('F16')['sources'][0]['values_loaded']
    assert not h.state.factors['F16'].judgement  # preload is not semantic validation
    assert not h.state.factors['F16'].dataset_ids


def test_ready_followup_precedes_next_unprepared_group(tmp_path):
    h = make(tmp_path)
    calls = []
    class Client:
        def next_actions(self, context):
            ids = list(context['factors'])
            calls.append(ids)
            return json.dumps({'actions':[{'factor_id':fid, 'action':
                {'action':'search','query':'cash','reason':'lookup'} if len(calls)==1 else
                {'action':'conclude','reason':'qualified','judgement':{
                    'summary':'Limited to available evidence','evidence_ids':[],'missing':['remaining sources']}}}
                for fid in ids]})
    h.client = Client()
    ids = ['F01','F02','F03','F04','F05','F06','F07']
    list(analyse_grouped(h, ids))
    assert calls[:2] == [ids[:6], ids[:6]]
    assert calls[2] == ['F07']
