import pytest
from credit_review.cell_bindings import BoundFoundation,index_tables,materialize,literal_value


def bound(row=1,column=1):
    return BoundFoundation(entity='Example',scope='CONSOLIDATED',
        period_cells=[{'source_id':'s','row':0,'column':1},{'source_id':'s','row':0,'column':2}],columns=[
        {'name':'부채','dtype':'number','unit':'천원','cells':[
            {'source_id':'s','row':row,'column':column},{'source_id':'s','row':1,'column':2}]}])


def test_cell_selection_keeps_original_magnitude_and_header():
    raw={'sources':{'s':{'kind':'table','text':'| 항목 | 2025 | 2024 |\n|---|---:|---:|\n| 부채 | 313,612,952 | 312,315,663 |'}}}
    indexed,matrices=index_tables(raw)
    data=materialize(bound(),matrices)
    assert data.rows==[{'기간':'2025','부채':313612952},{'기간':'2024','부채':312315663}]
    assert data.cell_sources[0]=={'기간':['s'],'부채':['s']}
    assert data.columns[1].unit=='천원'
    assert 'r1' in indexed['sources']['s']['text']
    assert 'r1' not in raw['sources']['s']['text']


def test_missing_or_non_numeric_cell_is_not_silently_replaced():
    matrices={'s':[['항목','2025','2024'],['부채','12','11']]}
    with pytest.raises(ValueError,match='out of bounds'): materialize(bound(row=9),matrices)
    with pytest.raises(ValueError,match='nonnumeric'): materialize(bound(column=0),matrices)
    assert literal_value('(1,200)','number')==-1200
    assert literal_value('-','number') is None
