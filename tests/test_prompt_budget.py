from copy import deepcopy
from credit_review.prompt_budget import compact_group_context


def test_compaction_preserves_source_text_provenance_and_analysis():
    context = {'review_date':'2026-04-07', 'sources':{'s1':{'id':'s1','text':'매출 123억원',
        'page':4,'document_id':'doc','published_at':'2026-03-31','structure':{'unit':'KRW'}}},
        'factors':{'F13':{'review_date':'2026-04-07','source_window':'repeated guidance',
            'state':{'factor_id':'F13','steps':3,'evidence_ids':['s1','older'],
                'inquiry':{'question':'growth?'},'error':'period mismatch','dataset_ids':['d1']}}},
        'datasets':{'d1':{'scope':'CONSOLIDATED','rows':[{'year':2025,'sales':123}],
            'cell_sources':[{'sales':['s1']}]}}, 'calculations':{'c1':{'status':'EXECUTED','result':3}}}
    original = deepcopy(context)
    compact = compact_group_context(context)
    assert context == original
    assert compact['sources']['s1']['text'] == '매출 123억원'
    assert compact['sources']['s1']['page'] == 4
    assert compact['datasets'] == context['datasets']
    assert compact['calculations'] == context['calculations']
    state = compact['factors']['F13']['state']
    assert state['evidence_ids'] == ['older']
    assert state['inquiry'] == {'question':'growth?'}
    assert state['error'] == 'period mismatch'
    assert 'steps' not in state
