from datetime import date
from credit_review.models import Source
from credit_review.section_context import attach_section_context


def source(sid, page, top, bottom, path=(), table=False, doc='doc', logical=None):
    return Source(id=sid,document_id=doc,page=page,text='original body',published_at=date(2026,1,1),
                  kind='table' if table else 'paragraph',metadata={'logical_table_id':logical,
                  'structured':{'section_path':list(path),'source':{'pages':[page],
                  'bboxes':[[0,top,100,bottom]]},'elements':[]}})


def test_heading_above_table_not_next_section_at_page_bottom():
    rows=[source('prior',1,650,720,['연결재무제표','연결 포괄손익계산서']),
          source('table',2,50,400,table=True),source('next',2,450,500,['연결 자본변동표'])]
    original={s.id:s for s in rows}
    result=attach_section_context(original)
    assert result['table'].metadata['structured']['section_path']==['연결재무제표','연결 포괄손익계산서']
    assert result['table'].metadata['section_context']['source_id']=='prior'
    assert original['table'].metadata['structured']['section_path']==[]
    assert result['table'].text==original['table'].text


def test_continued_table_keeps_first_segment_section_and_never_crosses_documents():
    rows=[source('h1',1,20,30,['요약별도재무정보']),source('t1',1,50,700,table=True,logical='L1'),
          source('h2',2,500,550,['연결재무제표']),source('t2',2,50,300,table=True,logical='L1'),
          source('other',2,600,700,table=True,doc='other')]
    result=attach_section_context({s.id:s for s in rows})
    assert result['t2'].metadata['structured']['section_path']==['요약별도재무정보']
    assert result['other'].metadata['structured']['section_path']==[]
