import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from review_documents import DocumentStore
from frozen_original_vector_sources import OriginalVectorStore


class FakeIndex:
    def __init__(self, documents, path):
        self.documents = documents
    def search(self, query, document_id, limit):
        return [(s['id'], 0.8) for s in self.documents[document_id]['sources']][:limit]


class OriginalSourceTests(unittest.TestCase):
    def test_original_rows_and_required_source_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = 'a'*64
            doc = {'id':key,'name':'sample.pdf','format':'pdf','sources':[
                {'id':key+'-p1-a','document_id':key,'page':1,'bbox':[0,0,10,20],
                 'text':'원문 표 2025 매출액 123','image_url':'/original-image'}]}
            raw = json.dumps(doc,ensure_ascii=False).encode()
            (root/(key+'.json')).write_bytes(raw)
            (root/'manifest.json').write_text(json.dumps({'files':{key+'.json':hashlib.sha256(raw).hexdigest()}}))
            uploads = [{'id':key,'name':'sample.pdf','priority':'매우 중요','required':True}]
            with patch.dict('sys.modules',{'frozen_vector_index':SimpleNamespace(VectorIndex=FakeIndex)}):
                adapter=OriginalVectorStore(DocumentStore(root),uploads,root,root/'index')
            self.assertEqual(adapter.get(key),doc)
            hits=adapter.select(['매출'],adapter.manifest(uploads),budget=1000,limit=3)
            self.assertEqual(len(hits),1)
            for field in ['id','text','page','bbox','image_url']:
                self.assertEqual(hits[0][field],doc['sources'][0][field])
            self.assertNotIn('structured',hits[0])
            (root/(key+'.json')).write_text('{}')
            with self.assertRaisesRegex(ValueError,'Frozen extracted document changed'):
                OriginalVectorStore(DocumentStore(root),uploads,root,root/'index')


if __name__=='__main__':unittest.main()
