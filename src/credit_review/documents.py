"""Source adapters. Structural JSON preserves existing engine output without copying it."""
import hashlib
import json
from datetime import date
from pathlib import Path

from .models import Source


def from_json(data: bytes) -> list[Source]:
    raw = json.loads(data)
    rows = raw["sources"] if isinstance(raw, dict) else raw
    sources = [Source.model_validate(r) for r in rows]
    if len({s.id for s in sources}) != len(sources):
        raise ValueError("Duplicate source IDs")
    return sources


def from_pdf_isolated(path: Path, published_at: date, artifact_dir: Path) -> list[Source]:
    """Load native PDF/model dependencies in a fresh interpreter after deployments."""
    import subprocess
    import sys
    import tempfile
    with tempfile.TemporaryDirectory(prefix='credit-pdf-') as temporary:
        result = Path(temporary) / 'sources.json'
        completed = subprocess.run([
            sys.executable, '-m', 'credit_review.pdf_worker', str(path.resolve()),
            published_at.isoformat(), str(artifact_dir.resolve()), str(result),
        ], capture_output=True, text=True, timeout=600)
        if completed.returncode:
            raise RuntimeError('PDF extraction failed: ' + completed.stderr[-6000:])
        return from_json(result.read_bytes())


def from_pdf(path: Path, published_at: date, artifact_dir: Path | None = None) -> list[Source]:
    """SPT v0.17 structural extraction, saved-model inference, hierarchical chunks."""
    from .vendor.spt017 import extract_document, PIPELINE_VERSION, MODEL_SHA256
    from .store import atomic_json
    master, chunks = extract_document(path)
    if artifact_dir is not None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        atomic_json(artifact_dir / "MASTER.json", master)
        atomic_json(artifact_dir / "chunks.json", {'chunks': [c.to_dict() for c in chunks]})
        atomic_json(artifact_dir / "manifest.json", {
            'pipeline': PIPELINE_VERSION, 'model_sha256': MODEL_SHA256,
            'pdf_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'published_at': str(published_at), 'pages': master['raw_document']['page_count'],
            'physical_tables': len(master['raw_document']['physical_tables']),
            'chunks': len(chunks), 'ocr': False})
    return sources_from_spt(master, chunks, hashlib.sha256(path.read_bytes()).hexdigest()[:16], published_at)


def sources_from_spt(master, chunks, document_id: str, published_at: date) -> list[Source]:
    """Keep original structural IDs in a document scope; global evidence IDs cannot collide."""
    from .vendor.spt017 import PIPELINE_VERSION
    result = []
    for page in master['raw_document']['pages']:
        result.append(Source(id=f"{document_id}_spt017_p{page['page']}", document_id=document_id,
            page=page['page'], kind='page', published_at=published_at,
            text='\n'.join(b['text'] for b in page['blocks']),
            metadata={'extractor': PIPELINE_VERSION, 'searchable': False, 'ocr': False,
                      'page_size': [page['width'], page['height']]}))
    tables = {t['table_id']: t for t in master['semantic_elements']['tables']}
    for chunk in chunks:
        structured = json.loads(chunk.document)
        meta = dict(chunk.metadata)
        meta.update(extractor=PIPELINE_VERSION, structured=structured, ocr=False,
                    source_document_id=document_id, embedding_text=chunk.embedding_text)
        if meta.get('physical_table_id'):
            table = tables[meta['physical_table_id']]
            meta['table_structure'] = {k: table.get(k) for k in (
                'header_depth', 'stub_column_count', 'status', 'inherited_header',
                'merge_evidence', 'logical_table_id')}
        page = min(meta['pages'])
        result.append(Source(id=f"{document_id}_spt017_{chunk.chunk_id}", document_id=document_id,
            page=page, text=chunk.embedding_text, kind='table' if meta['content_type']=='table' else 'paragraph',
            parent_id=f"{document_id}_spt017_p{page}", published_at=published_at, metadata=meta))
    return result


def from_spt_blocks(blocks, document_id: str, published_at: date) -> list[Source]:
    """Bridge for PocDocumentExtractor.extract output; original metadata is retained."""
    result = []
    for i, block in enumerate(blocks):
        raw = vars(block) if hasattr(block, "__dict__") else dict(block)
        content = raw.get("text", raw.get("content", ""))
        page = raw.get("page", raw.get("page_number", 1)) or 1
        result.append(Source(id=f"{document_id}_{i}", document_id=document_id,
            page=int(page), text=str(content), kind=str(raw.get("kind", "paragraph")),
            published_at=published_at, metadata=raw))
    return result
