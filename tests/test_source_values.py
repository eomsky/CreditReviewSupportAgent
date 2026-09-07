from types import SimpleNamespace
import pytest
from credit_review.source_values import validate_table_values, numeric_literals, currency_unit


def sample(value=313612952, unit='천원'):
    data = SimpleNamespace(value_type='ACTUAL', columns=[SimpleNamespace(name='debt', dtype='number', unit=unit)],
                           rows=[{'debt':value}], cell_sources=[{'debt':['s']}])
    sources = {'s':{'metadata':{'structured':{'elements':[{'type':'table',
        'content':{'value':'| 총차입금 | 313,612,952 |\n| 현금차감 | (164,134,328) |'},
        'units':[{'scope':'table','text':'(단위 : 천원)'}]}]}}}}
    return data, sources


def test_thousandfold_unit_error_rejected_before_calculation():
    validate_table_values(*sample())
    with pytest.raises(ValueError, match='value not found'):
        validate_table_values(*sample(313613))
    with pytest.raises(ValueError, match='unit conflicts'):
        validate_table_values(*sample(unit='백만원'))


def test_source_sign_and_decimal_values_preserved():
    assert numeric_literals('(1,200) 0.25 −9') == {-1200, .25, -9}
    validate_table_values(*sample(-164134328))
    assert currency_unit('(단위:십억원)') == 'KRW_BILLION'


def test_legacy_sources_not_rejected_by_table_only_checker():
    data, _ = sample()
    validate_table_values(data, {'s':{'text':'debt'}})
