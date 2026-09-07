"""Bounded process-level page extraction; retain the v0.17 page/cell records."""
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import fitz


def _range(args):
    from .vendor.spt017.extractor import PDFExtractor
    path,start,end=args
    return PDFExtractor().extract(path,start,end)


def extract_raw(path,workers=1):
    from .vendor.spt017.extractor import PDFExtractor
    workers=max(1,min(4,int(workers)))
    if workers==1:
        return PDFExtractor().extract(str(path))
    path=str(Path(path).resolve())
    with fitz.open(path) as doc:
        count=len(doc)
    if count<16:
        return PDFExtractor().extract(path)
    # Each process owns its document; PyMuPDF objects never cross threads/processes.
    ranges=[(path,start,min(start+32,count)) for start in range(0,count,32)]
    pages=[]; tables=[]
    with ProcessPoolExecutor(max_workers=min(workers,len(ranges)),
                             mp_context=multiprocessing.get_context('spawn')) as pool:
        for part in pool.map(_range,ranges):
            pages.extend(part['pages'])
            tables.extend(part['physical_tables'])
    if [page['page'] for page in pages]!=list(range(1,count+1)):
        raise ValueError('Parallel PDF extraction lost or reordered pages')
    return {'source_pdf':Path(path).name,'page_count':count,'pages':pages,'physical_tables':tables}
