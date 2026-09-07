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


def from_pdf(path: Path, published_at: date) -> list[Source]:
    """Baseline adapter, explicitly NOT a full merged-table/OCR implementation."""
    import pymupdf
    doc_id = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    result = []
    with pymupdf.open(path) as pdf:
        for page_no, page in enumerate(pdf, 1):
            parent = f"{doc_id}_p{page_no}"
            text = page.get_text("text")
            result.append(Source(id=parent, document_id=doc_id, page=page_no, text=text,
                                 kind="page", published_at=published_at,
                                 metadata={"filename": path.name, "extractor": "pymupdf_baseline", "ocr": False}))
            for i, block in enumerate(page.get_text("blocks")):
                if block[6] == 0 and block[4].strip():
                    result.append(Source(id=f"{parent}_b{i}", document_id=doc_id, page=page_no,
                        parent_id=parent, kind="paragraph", text=block[4], published_at=published_at,
                        metadata={"bbox": list(block[:4])}))
            for i, table in enumerate(page.find_tables().tables):
                rows = table.extract()
                result.append(Source(id=f"{parent}_t{i}", document_id=doc_id, page=page_no,
                    parent_id=parent, kind="table", text=json.dumps(rows, ensure_ascii=False),
                    published_at=published_at, metadata={"rows": rows, "bbox": list(table.bbox),
                    "warning": "Headers, units and cross-page continuity require semantic validation"}))
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
