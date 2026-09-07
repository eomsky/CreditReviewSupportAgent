from datetime import date
import json
import pytest
from credit_review.models import Source, Action
from credit_review.harness import Harness
from credit_review.table_access import search_text
from credit_review.grouped import group_context


def source():
    return Source(id='table1', document_id='doc', page=4, kind='table',
        published_at=date(2026, 3, 31), text='sales 987654321', metadata={'structured':{
        'section_path':['Consolidated results'], 'elements':[{'type':'table',
        'title':'Revenue', 'physical_table_id':'t1', 'segment':{'part_index':1,'part_count':2},
        'content':{'value':'| year | revenue |\n|2025|987654321|'},
        'units':[{'text':'KRW million','scope':'table'}], 'notes':[{'text':'restated'}],
        'hierarchy':{'columns':[{'column_id':'c1','path':['2025'],'role':'measure'}],
                     'rows':[{'row_id':'r1','path':['revenue']}],
                     'cells':[{'value':'987654321'}]}}]}})


def test_discovery_index_excludes_values_but_preserves_labels():
    text = search_text(source())
    assert '987654321' not in text
    for value in ('Revenue', 'revenue', '2025', 'KRW million'):
        assert value in text
    assert 'part_count' not in text and 'table1' not in text
    from credit_review.table_access import table_card
    card = table_card(source().model_dump(mode='json'))
    assert card['locator']['source_id']=='table1'
    assert card['tables'][0]['segment']['part_count']==2


def test_explicit_read_restores_values_and_is_shared(tmp_path):
    h = Harness.create(tmp_path, 'test', date(2026,4,7), [source()], None)
    h.apply('F13', Action(action='search', query='revenue', reason='find'), 'test')
    card = h.context('F13')['sources'][0]
    assert card['values_loaded'] is False and card['text'] == ''
    with pytest.raises(ValueError, match='discovery card'):
        h.require_table_read({'table1'})
    h.apply('F13', Action(action='read', source_ids=['table1'], reason='values'), 'test')
    h.require_table_read({'table1'})
    h.state.factors['F14'].recent_source_ids = ['table1']
    h.source_excerpt_chars = 5
    actual = group_context(h, ['F13','F14'])['sources']['table1']
    assert actual['values_loaded'] is True
    assert '987654321' in actual['text']
    assert actual['table_notes'] == [{'text':'restated'}]
    assert h.retriever.sources['table1'].text == 'sales 987654321'
    # Original cell provenance is retained in the source artifact.
    assert 'cells' in json.dumps(h.retriever.sources['table1'].metadata)


def test_cached_search_does_not_count_as_read(tmp_path):
    from credit_review.shared_work import SharedWork
    h = Harness.create(tmp_path, 'test', date(2026,4,7), [source()], None)
    memory = SharedWork(h)
    action = Action(action='search', query='revenue', reason='find')
    result = h.apply('F13', action, 'test')
    memory.record('F13', action, 'test', result)
    assert memory.reuse_exact('F14', action, 'test') == result
    assert not h.state.factors['F14'].read_source_ids
    assert not h.context('F14')['sources'][0]['values_loaded']
