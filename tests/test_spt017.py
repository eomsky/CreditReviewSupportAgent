from datetime import date
from pathlib import Path
import json
import pytest
from credit_review.vendor.spt017 import StructuralBuilder, ChunkBuilder, ChunkRepresentationLevel, load_boundary_model
from credit_review.documents import sources_from_spt, from_pdf
from credit_review.retrieval import Retriever


def raw_document():
    matrix=[['Category','2024','2025'],['Revenue','100','120'],['Profit','10','15']]
    cells=[{'row':r,'column':c,'bbox':[50+c*100,200+r*25,150+c*100,225+r*25]}
           for r in range(3) for c in range(3)]
    return {'source_pdf':'synthetic.pdf','page_count':1,
            'pages':[{'page':1,'width':600.,'height':800.,'body_font_size':10.,'blocks':[]}],
            'physical_tables':[{'table_id':'P0001_T001','page':1,'page_width':600.,'page_height':800.,
                                'bbox':[50.,200.,350.,275.],'matrix':matrix,'cell_geometry':cells}]}


def test_saved_model_and_real_structural_chunk_contract():
    assert load_boundary_model()['version']=='v0.17'
    master=StructuralBuilder().build(raw_document())
    assert master['model_info']['mode']=='LOAD'
    chunks=ChunkBuilder(representation_level=ChunkRepresentationLevel.HIERARCHICAL).build(master)
    assert chunks
    payload=json.loads(chunks[0].document)
    table=payload['elements'][0]
    assert table['type']=='table'
    assert all(k in table for k in ['title','units','notes','hierarchy','segment'])
    assert payload['source']['object_ids']==['P0001_T001']
    hierarchy=table['hierarchy']
    assert hierarchy['columns'] and hierarchy['rows'] and hierarchy['cells']
    columns={c['column_id'] for c in hierarchy['columns']}
    assert all(c['column_id'] in columns for c in hierarchy['cells'])


def test_document_namespace_and_page_retrieval():
    master=StructuralBuilder().build(raw_document())
    chunks=ChunkBuilder(representation_level=2).build(master)
    one=sources_from_spt(master,chunks,'document_a',date(2026,1,1))
    two=sources_from_spt(master,chunks,'document_b',date(2026,1,1))
    assert not ({s.id for s in one} & {s.id for s in two})
    retriever=Retriever(one+two,date(2026,1,2))
    assert all(s.kind!='page' for s in retriever.rows)
    assert retriever.read([one[-1].id])[-1]['kind']=='page'
    assert one[-1].metadata['structured']['elements'][0]['hierarchy']['cells']


def test_merge_safe_guard_preserved(monkeypatch):
    builder=StructuralBuilder()
    monkeypatch.setattr(builder,'_restore_merge_spans',lambda table:[{'row':0,'column':1,'row_span':3,'col_span':2}])
    assert builder._crosses_measure_vertical_merge_v017({},2,1)
    assert not builder._crosses_measure_vertical_merge_v017({},3,1)


def test_adapter_saves_master_and_chunks(tmp_path,monkeypatch):
    import credit_review.vendor.spt017 as upstream
    master=StructuralBuilder().build(raw_document())
    chunks=ChunkBuilder(representation_level=2).build(master)
    monkeypatch.setattr(upstream,'extract_document',lambda path:(master,chunks))
    pdf=tmp_path/'input.pdf';pdf.write_bytes(b'synthetic transport fixture')
    result=from_pdf(pdf,date(2026,1,1),tmp_path/'assets')
    assert result and all(s.metadata['ocr'] is False for s in result)
    saved=json.loads((tmp_path/'assets'/'MASTER.json').read_text(encoding='utf-8'))
    assert saved['raw_document']==master['raw_document']
    assert json.loads((tmp_path/'assets'/'manifest.json').read_text())['pipeline']=='spt017-structural-v1'


def test_cached_inference_preserves_structure_and_scalar_semantics():
    from copy import deepcopy
    from credit_review.spt_inference_cache import CachedStructuralBuilder
    raw=raw_document()
    # Two physical segments exercise document-wide continuity and header inference.
    second=deepcopy(raw['physical_tables'][0])
    second.update(table_id='P0002_T001',page=2)
    second['matrix']=[['Category','2024','2025'],['Assets','1,000','1,200'],['Debt','(10)','-']]
    raw['physical_tables'].append(second)
    raw['pages'].append({**raw['pages'][0],'page':2}); raw['page_count']=2
    plain=StructuralBuilder(); cached=CachedStructuralBuilder()
    assert plain.build(deepcopy(raw))==cached.build(deepcopy(raw))
    for value in [None,0,False,True,1,1.0,' 1,234 ', '(123)', '2025.01.01','해당없음','USD 10',[],{'x':1}]:
        for name in ['_clean','_numeric','_value_kind','_value_kind_v015','_content_type']:
            assert getattr(plain,name)(value)==getattr(cached,name)(value)
