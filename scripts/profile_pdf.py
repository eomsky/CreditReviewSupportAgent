"""Time the preserved v0.17 stages separately, without LLM calls or PDF writes."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from credit_review.vendor.spt017 import PDFExtractor,StructuralBuilder,ChunkBuilder,ChunkRepresentationLevel


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('pdf',type=Path)
    parser.add_argument('output',type=Path); parser.add_argument('--master',type=Path)
    parser.add_argument('--cached-builder',action='store_true')
    parser.add_argument('--workers',type=int,choices=range(1,5),default=1)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    timings={}; start=perf_counter()
    if args.master:
        raw=json.loads(args.master.read_text(encoding='utf-8'))['raw_document']
        timings['raw_reused']=True
    else:
        from credit_review.pdf_parallel import extract_raw
        raw=extract_raw(args.pdf,args.workers)
        timings['raw_reused']=False
    timings['raw_seconds']=perf_counter()-start
    print('RAW',json.dumps(timings),flush=True)
    builder=StructuralBuilder
    if args.cached_builder:
        from credit_review.spt_inference_cache import CachedStructuralBuilder
        builder=CachedStructuralBuilder
    start=perf_counter(); master=builder().build(raw)
    timings['structure_seconds']=perf_counter()-start
    print('STRUCTURE',timings['structure_seconds'],flush=True)
    start=perf_counter(); chunks=ChunkBuilder(representation_level=ChunkRepresentationLevel.HIERARCHICAL).build(master)
    timings['chunks_seconds']=perf_counter()-start
    timings.update(pages=raw['page_count'],tables=len(raw['physical_tables']),chunks=len(chunks),
                   pdf_sha256=hashlib.sha256(args.pdf.read_bytes()).hexdigest())
    (args.output/'timings.json').write_text(json.dumps(timings,indent=2))
    (args.output/'MASTER.json').write_text(json.dumps(master,ensure_ascii=False),encoding='utf-8')
    (args.output/'chunks.json').write_text(json.dumps([c.to_dict() for c in chunks],ensure_ascii=False),encoding='utf-8')
    print('RESULT',json.dumps(timings),flush=True)


if __name__=='__main__': main()
