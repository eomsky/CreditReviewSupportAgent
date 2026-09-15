"""C4: frozen extraction with dense/keyword retrieval; no SPT transformation."""
import hashlib
import json
from pathlib import Path

from frozen_structured_sources import StructuredStore


class OriginalVectorStore(StructuredStore):
    def __init__(self, original, uploads, frozen, vector_path):
        self.original = original
        self.root = original.root
        self.documents = {}
        self.retrievers = {}
        self.mode = 'dense'
        frozen = Path(frozen)
        hashes = json.loads((frozen/'manifest.json').read_text(encoding='utf-8'))['files']
        self.source_hashes = {}
        for item in uploads:
            key = item['id']
            name = key+'.json'
            raw = (frozen/name).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != hashes[name]:
                raise ValueError('Frozen extracted document changed: '+key)
            doc = json.loads(raw)
            original.cache[key] = doc
            self.source_hashes[key] = digest
            if doc['format'] == 'pdf':
                self.documents[key] = doc
        self.keyword = original
        from frozen_vector_index import VectorIndex
        self.vector = VectorIndex(self.documents, vector_path)
