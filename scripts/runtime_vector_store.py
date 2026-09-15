"""Unpromoted runtime adapter: original extraction, incremental local vector index."""
import hashlib,json,threading,uuid
from pathlib import Path
from time import perf_counter
from importlib.metadata import version
from frozen_vector_index import VectorIndex
from frozen_page_vector_sources import PageVectorStore,compact_layout


class IncrementalIndex(VectorIndex):
    def __init__(self,path):
        super().__init__({},path)
        from qdrant_client import models
        from tokenizers import Tokenizer
        self.lock=threading.RLock()
        self.path=Path(path)
        identity=json.dumps([self.info['model_file_hashes'],version('fastembed'),'mean-pooling','400/350'],sort_keys=True)
        self.collection='runtime_'+hashlib.sha256(identity.encode()).hexdigest()[:24]
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(self.collection,vectors_config=models.VectorParams(size=384,distance=models.Distance.COSINE))
        self.state_path=self.path/(self.collection+'.json')
        self.fingerprints=json.loads(self.state_path.read_text(encoding='utf-8')) if self.state_path.exists() else {}
        cache=self.model_cache
        self.tokenizer=Tokenizer.from_file(str(next(cache.rglob('tokenizer.json'))))
        self.tokenizer.no_truncation();self.tokenizer.no_padding()
        self.metrics=[]
        self.info.update(collection=self.collection,mode='incremental_by_document',documents=len(self.fingerprints))

    def ensure(self,documents):
        from qdrant_client import models
        with self.lock:
            for document_id,document in documents.items():
                began=perf_counter()
                sources=[(s['id'],s['text']) for s in document['sources']]
                digest=hashlib.sha256(json.dumps(sources,ensure_ascii=False).encode()).hexdigest()
                if self.fingerprints.get(document_id)==digest:continue
                parts=[]
                for source_id,text in sources:
                    offsets=[(a,b) for a,b in self.tokenizer.encode(text,add_special_tokens=False).offsets if b>a]
                    for index in range(0,len(offsets),350):
                        window=offsets[index:index+400]
                        parts.append((source_id,index,text[window[0][0]:window[-1][1]]))
                for offset in range(0,len(parts),32):
                    batch=parts[offset:offset+32]
                    vectors=list(self.model.embed([p[2] for p in batch],batch_size=16))
                    points=[]
                    for (source_id,index,text),vector in zip(batch,vectors):
                        point_id=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{document_id}:{digest}:{source_id}:{index}'))
                        points.append(models.PointStruct(id=point_id,vector=vector.tolist(),payload={'document_id':document_id,'source_id':source_id,'fingerprint':digest}))
                    self.client.upsert(self.collection,points=points)
                self.fingerprints[document_id]=digest
                temporary=self.state_path.with_suffix('.tmp')
                temporary.write_text(json.dumps(self.fingerprints),encoding='utf-8');temporary.replace(self.state_path)
                self.metrics.append({'document_id':document_id,'parts':len(parts),'seconds':perf_counter()-began})
                self.info.update(documents=len(self.fingerprints),indexed_this_session=list(self.metrics))

    def search(self,query,document_id,limit):
        from qdrant_client import models
        with self.lock:
            digest=self.fingerprints.get(document_id)
            if digest is None:return []
            if query not in self.queries:self.queries[query]=list(self.model.query_embed(query))[0].tolist()
            matches=[models.FieldCondition(key=k,match=models.MatchValue(value=v)) for k,v in [('document_id',document_id),('fingerprint',digest)]]
            hits=self.client.query_points(self.collection,query=self.queries[query],query_filter=models.Filter(must=matches),limit=max(64,limit*8)).points
            chosen={}
            for hit in hits:
                chosen.setdefault(hit.payload['source_id'],hit.score)
                if len(chosen)>=limit:break
            return list(chosen.items())


class RuntimePageStore(PageVectorStore):
    def __init__(self,original,index_path):
        self.original=self.keyword=original
        self.root=original.root
        self.documents={}
        self.vector=IncrementalIndex(index_path)
        self.lock=threading.RLock()

    def get(self,key):
        document=self.original.get(key)
        if document.get('format')=='pdf':
            return {**document,'sources':[{**s,'text':compact_layout(s['text'])} for s in document['sources']]}
        return document

    def select(self,terms,manifest,budget=16000,limit=24):
        with self.lock:
            docs={m['id']:self.original.get(m['id']) for m in manifest}
            pdfs={key:doc for key,doc in docs.items() if doc.get('format')=='pdf'}
            self.vector.ensure(pdfs)
            self.documents.update(pdfs)
            return super().select(terms,manifest,budget,limit)
