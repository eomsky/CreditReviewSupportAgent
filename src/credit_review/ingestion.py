"""Upload-time, content-addressed preparation. No Streamlit calls in workers."""
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pathlib import Path
from time import monotonic
import hashlib
import json

from .documents import from_pdf_isolated, from_json
from .store import atomic_json
from .vendor.spt017 import PIPELINE_VERSION

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='pdf-prepare')
_lock = Lock()
_jobs = {}


def prepare_upload(root, content, filename, published, retry=False):
    digest = hashlib.sha256(content).hexdigest()
    key = (str(Path(root).resolve()), digest, str(published), PIPELINE_VERSION, filename.lower().endswith('.json'))
    with _lock:
        old = _jobs.get(key)
        if old and not (retry and old.done() and old.exception()):
            return old
        future = _pool.submit(_prepare, Path(root), content, filename, published, digest)
        _jobs[key] = future
        for previous in list(_jobs):
            if len(_jobs) <= 8:
                break
            if previous != key and _jobs[previous].done():
                del _jobs[previous]
        return future


def _prepare(root, content, filename, published, digest):
    started = monotonic()
    folder = root / 'documents' / digest / PIPELINE_VERSION
    cache = folder / (str(published) + '.json')
    if filename.lower().endswith('.json'):
        rows, hit = from_json(content), False
    elif cache.exists():
        rows, hit = from_json(cache.read_bytes()), True
    else:
        folder.mkdir(parents=True, exist_ok=True)
        pdf = folder / 'original.pdf'
        pdf.write_bytes(content)
        # Adopt already prepared v0.17 documents from the prior case-scoped cache.
        candidates = list(folder.glob('*.json')) + list(root.glob(f'cases/*/sources/{digest}_*_{PIPELINE_VERSION}.json'))
        if candidates:
            rows = [s.model_copy(update={'published_at': published}) for s in from_json(candidates[0].read_bytes())]
            hit = True
        else:
            rows = from_pdf_isolated(pdf, published, folder / 'structure')
            hit = False
        atomic_json(cache, {'sources': [s.model_dump(mode='json') for s in rows]})
    # Build the same index the report will reuse, off the interactive UI path.
    from .retrieval import Retriever
    Retriever(rows, published)
    return {'sources': [s.model_dump(mode='json') for s in rows],
            'cached': hit, 'seconds': monotonic()-started, 'document_hash': digest}
