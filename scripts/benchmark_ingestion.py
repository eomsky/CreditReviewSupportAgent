"""Measure native v0.17 PDF preparation separately from generation."""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from time import monotonic
from uuid import uuid4
from credit_review.documents import from_pdf_isolated
from credit_review.retrieval import Retriever
from credit_review.store import atomic_json

p=argparse.ArgumentParser()
p.add_argument('pdf',type=Path,nargs='?')
a=p.parse_args()
pdf=a.pdf or next(Path('workspace/documents').glob('*/**/original.pdf'))
out=Path('workspace/benchmarks/ingestion')/uuid4().hex
out.mkdir(parents=True)
start=monotonic()
rows=from_pdf_isolated(pdf,date(2026,3,31),out/'structure')
extracted=monotonic()
Retriever(rows,date(2026,4,7))
result={'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'bytes':pdf.stat().st_size,
    'pages':sum(s.kind=='page' for s in rows),'sources':len(rows),'extraction_seconds':extracted-start,
    'index_seconds':monotonic()-extracted,'total_seconds':monotonic()-start,
    'ocr':False,'cached_extraction':False,'note':'Fresh extraction subprocess; model/filesystem caches may be warm.'}
atomic_json(out/'summary.json',result)
print(json.dumps(result),flush=True)
