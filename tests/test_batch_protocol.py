import json
import pytest
from test_harness import make
from credit_review.batch_protocol import unpack_dataset_rows
from credit_review.llm import ColabClient
from credit_review.grouped import group_context


def capture_schema(sources):
    captured = {}
    client = object.__new__(ColabClient)
    def complete(prompt, context, schema, **kwargs):
        captured.update(schema)
        return '{}'
    client.complete = complete
    client.next_actions({'factors':{'F13':{}}, 'sources':sources})
    return captured


def test_schema_excludes_only_visible_complete_bodies_from_read():
    schema = capture_schema({'complete':{'read_complete':True},
                             'discovery':{'read_complete':False},
                             'excerpt':{'read_complete':True,'excerpt_only':True}})
    choices = schema['$defs']['FactorAction']['anyOf'][0]['properties']['action']['anyOf']
    read = next(b for b in choices if b['properties']['action']['enum']==['read'])
    assert set(read['properties']['source_ids']['items']['enum']) == {'discovery','excerpt'}
    schema = capture_schema({'complete':{'read_complete':True}})
    choices = schema['$defs']['FactorAction']['anyOf'][0]['properties']['action']['anyOf']
    assert not any(b['properties']['action']['enum']==['read'] for b in choices)


def test_three_rows_keep_individual_provenance_and_shape_validation():
    from credit_review.models import Dataset
    data = {'name':'cash','description':'cash','entity':'company','scope':'CONSOLIDATED',
            'value_type':'ACTUAL', 'columns':[{'name':'year','dtype':'integer'},{'name':'cash','dtype':'number'}],
            'period_column':'year', 'records':[
                {'values':{'year':2023+i,'cash':100+i}, 'sources':{'year':[f's{i}'],'cash':[f's{i}']}}
                for i in range(3)]}
    wire = json.dumps({'actions':[{'factor_id':'F13','action':{'action':'dataset','dataset':data}}]})
    unpacked = json.loads(unpack_dataset_rows(wire))['actions'][0]['action']['dataset']
    result = Dataset.model_validate(unpacked)
    assert [r['cash'] for r in result.cell_sources] == [['s0'],['s1'],['s2']]
    assert len(result.rows) == 3
    unpacked['cell_sources'][1] = {}
    with pytest.raises(ValueError, match='provenance'):
        Dataset.model_validate(unpacked)
    schema = capture_schema({'s0':{},'s1':{},'s2':{}})['$defs']['Dataset']
    assert 'records' in schema['required'] and 'rows' not in schema['properties']
    assert set(schema['properties']['records']['items']['required']) == {'values','sources'}


def test_all_requested_read_bodies_survive_group_context(tmp_path):
    h = make(tmp_path)
    from credit_review.retrieval import Retriever
    source = next(iter(h.retriever.sources.values()))
    h.retriever = Retriever([source.model_copy(update={'id':f's{i}'}) for i in range(3)], h.state.review_date)
    ids = list(h.retriever.sources)[:3]
    assert len(ids) == 3
    factor = h.state.factors['F13']
    factor.evidence_ids = factor.recent_source_ids = factor.read_source_ids = ids
    sources = group_context(h,['F13'])['sources']
    assert set(ids).issubset(sources)
    assert all(sources[sid]['read_complete'] for sid in ids)
