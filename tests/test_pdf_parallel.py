import fitz
from credit_review.pdf_parallel import extract_raw


def test_parallel_preserves_page_ids_table_geometry_and_order(tmp_path):
    path=tmp_path/'pages.pdf'
    with fitz.open() as doc:
        for number in range(35):
            page=doc.new_page()
            page.insert_text((60,60),f'Page {number+1}')
            for x in (60,160,260):
                page.draw_line((x,90),(x,150))
            for y in (90,120,150):
                page.draw_line((60,y),(260,y))
            page.insert_text((70,110),'Year')
            page.insert_text((170,110),'Value')
            page.insert_text((70,140),'2025')
            page.insert_text((170,140),str(number*100))
        doc.save(path)
    serial=extract_raw(path,1)
    parallel=extract_raw(path,2)
    assert serial==parallel
    assert len(parallel['pages'])==35
    assert len(parallel['physical_tables'])==35
    assert parallel['physical_tables'][-1]['table_id']=='P0035_T001'
