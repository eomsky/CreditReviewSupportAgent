from types import SimpleNamespace
import pytest
from credit_review.evidence_scope import explicit_scope,validate_source_scopes


def source(title,path=()):
    return {'metadata':{'structured':{'section_path':list(path),
        'elements':[{'type':'table','title':title}]},
        'page_opening':{'text':'2. 연결재무제표\n연결 재무상태표'}}}


def test_table_title_outweighs_next_section_on_same_page():
    row=source('나. 요약별도재무정보',['2. 연결재무제표'])
    assert explicit_scope(row)['scope']=='SEPARATE'
    assert explicit_scope(source('가. 요약연결재무정보'))['scope']=='CONSOLIDATED'
    assert explicit_scope(source('포괄손익계산서'))['scope']=='UNKNOWN'
    assert explicit_scope(source('연결대상 종속회사 개황'))['scope']=='UNKNOWN'


def test_mixed_statement_data_rejected_before_python():
    sources={'s':source('요약별도재무정보'),'c':source('연결 재무상태표')}
    data=SimpleNamespace(scope='CONSOLIDATED',cell_sources=[{'sales':['s'],'debt':['c']}])
    with pytest.raises(ValueError,match='mixes'): validate_source_scopes(data,sources)
    data.cell_sources=[{'sales':['s']}]
    with pytest.raises(ValueError,match='conflicts'): validate_source_scopes(data,sources)
    data.scope='SEPARATE'
    validate_source_scopes(data,sources)


def test_unknown_scope_does_not_become_consolidated():
    assert explicit_scope(source('재무상태표'))['scope']=='UNKNOWN'
    assert explicit_scope(source('요약재무정보',['별도 재무제표']))['scope']=='SEPARATE'
