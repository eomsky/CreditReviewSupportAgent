"""Persistent local Qdrant index used only by the controlled C3 candidate."""
import hashlib
import json
from pathlib import Path
from time import perf_counter

MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'


class VectorIndex:
    def __init__(self,documents,path):
        from fastembed import TextEmbedding
        from qdrant_client import QdrantClient, models
        from tokenizers import Tokenizer
        root=Path(__file__).resolve().parents[1]
        # Harness copies live two directories deeper. Keep model cache independent.
        while not (root/'workspace/review_documents').exists():
            if root==root.parent:raise ValueError('Experiment workspace not found')
            root=root.parent
        cache=root/'outputs/frozen_candidates/embedding-model-cache'
        self.model_cache=cache
        start=perf_counter()
        self.model=TextEmbedding(MODEL,cache_dir=str(cache),threads=4)
        files=[p for p in cache.rglob('*') if p.is_file() and p.suffix in ('.json','.onnx')]
        hashes={str(p.relative_to(cache)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        token_file=next(p for p in files if p.name=='tokenizer.json')
        tokenizer=Tokenizer.from_file(str(token_file));tokenizer.no_truncation();tokenizer.no_padding()
        parts=[]
        for digest,doc in sorted(documents.items()):
            for source in doc['sources']:
                text=source['text']
                offsets=[(a,b) for a,b in tokenizer.encode(text,add_special_tokens=False).offsets if b>a]
                for i in range(0,len(offsets),350):
                    window=offsets[i:i+400]
                    parts.append((digest,source['id'],text[window[0][0]:window[-1][1]]))
        identity=hashlib.sha256(json.dumps([MODEL,hashes,parts],ensure_ascii=False).encode()).hexdigest()
        path=Path(path);path.mkdir(parents=True,exist_ok=True)
        self.client=QdrantClient(path=str(path/'db'))
        self.collection='cells_'+identity[:24]
        exists=self.client.collection_exists(self.collection)
        reused=exists and self.client.count(self.collection,exact=True).count==len(parts)
        if not reused:
            if not exists:self.client.create_collection(self.collection,vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))
            for offset in range(0,len(parts),32):
                batch=parts[offset:offset+32]
                vectors=list(self.model.embed([r[2] for r in batch],batch_size=16))
                self.client.upsert(self.collection,points=[models.PointStruct(id=offset+i,vector=v.tolist(),payload={'document_id':d,'source_id':s}) for i,((d,s,t),v) in enumerate(zip(batch,vectors))])
        self.info={'model':MODEL,'model_file_hashes':hashes,'parts':len(parts),'index_reused':reused,'index_seconds':perf_counter()-start,'collection':self.collection}
        (path/'manifest.json').write_text(json.dumps(self.info,ensure_ascii=False,indent=2),encoding='utf-8')
        self.queries={}

    def search(self,query,document_id,limit):
        from qdrant_client import models
        if query not in self.queries:self.queries[query]=list(self.model.query_embed(query))[0].tolist()
        hits=self.client.query_points(self.collection,query=self.queries[query],
            query_filter=models.Filter(must=[models.FieldCondition(key='document_id',match=models.MatchValue(value=document_id))]),limit=max(64,limit*8)).points
        selected={}
        for hit in hits:
            selected.setdefault(hit.payload['source_id'],hit.score)
            if len(selected)>=limit:break
        return list(selected.items())
