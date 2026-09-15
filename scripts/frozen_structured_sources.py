"""Isolated candidate adapter: SPT table context and sparse search, never live writes."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace


class StructuredStore:
    def __init__(self, original, artifact_paths, mode='keyword', vector_path=None):
        self.original = original
        self.root = original.root
        self.documents = {}
        self.retrievers = {}
        self.mode = mode
        from credit_review.documents import sources_from_spt
        from credit_review.retrieval import Retriever
        for digest, folder in artifact_paths.items():
            folder = Path(folder)
            master = json.loads((folder/'MASTER.json').read_text(encoding='utf-8'))
            manifest = json.loads((folder/'timings.json').read_text(encoding='utf-8'))
            import hashlib
            if manifest['pdf_sha256'] != digest or hashlib.sha256((self.root/(digest+'.bin')).read_bytes()).hexdigest()!=digest:
                raise ValueError('Structural artifact document hash mismatch')
            chunks=[SimpleNamespace(**c) for c in json.loads((folder/'chunks.json').read_text(encoding='utf-8'))]
            sources=sources_from_spt(master,chunks,digest,date.today())
            if mode=='sparse':self.retrievers[digest]=Retriever(sources,date.today())
            tables={t['table_id']:t for t in master['semantic_elements']['tables']}
            doc=original.get(digest)
            # Both C2 and C3 use exactly the SPT corpus, not a mixture with the
            # old three-band PDF extraction. Non-PDF documents stay unchanged.
            rows=[]
            for s in sources:
                if s.kind=='page': continue
                meta=s.metadata; table=tables.get(meta.get('physical_table_id'))
                # Header provenance can belong to an earlier page; image locator cannot.
                page=table['page'] if table else s.page
                source_pages=meta.get('pages',[page])
                openings=[]
                for p in source_pages:
                    blocks=master['raw_document']['pages'][p-1]['blocks']
                    openings.append(f'원문 {p}쪽 도입부:\n'+'\n'.join(b['text'] for b in blocks)[:900])
                text='\n'.join(openings)+'\n'+s.text
                if table: text+='\n파서 구조 상태: '+str(table.get('status','UNKNOWN'))+' (의미 검증 결과가 아님)'
                bbox=table['bbox'] if table else (meta.get('bboxes') or [[0,0,595,842]])[0]
                rows.append({'id':s.id.replace(digest+'_',digest+'-',1),'document_id':digest,'document_name':doc['name'],
                    'page':page,'bbox':bbox,'text':text,'format':'pdf',
                    'structured':meta.get('structured'), 'parser_status':table.get('status','UNKNOWN') if table else None,
                    'table_coverage':bool(table),'structural_source':True})
            self.documents[digest]={**doc,'sources':rows}
        from review_documents import DocumentStore
        self.keyword=DocumentStore(self.root)
        self.keyword.cache.update(original.cache)
        self.keyword.cache.update(self.documents)
        if mode=='dense':
            from frozen_vector_index import VectorIndex
            self.vector=VectorIndex(self.documents,vector_path)

    def get(self,key): return self.documents.get(key) or self.original.get(key)
    def manifest(self,items): return self.original.manifest(items)

    def select(self,terms,manifest,budget=16000,limit=24):
        if self.mode=='keyword':return self.keyword.select(terms,manifest,budget,limit)
        from review_documents import DocumentError, PRIORITIES
        # Keep original candidates and add structural hits; fill each document's
        # required slot before remaining priority/rank-ordered candidates.
        groups={}
        for meta in manifest:
            original=self.keyword.select(terms,[meta],budget=budget,limit=limit)
            structural=[]
            if self.mode=='dense' and meta['id'] in self.documents:
                lookup={s['id']:s for s in self.get(meta['id'])['sources']}
                for sid,score in self.vector.search(' '.join(terms),meta['id'],limit):
                    s=lookup[sid]
                    structural.append({**s,'document_name':meta['name'],'metadata':meta,
                        'selection_relevance':score,'retrieval_mode':'dense_keyword'})
            elif meta['id'] in self.retrievers:
                lookup={s['id']:s for s in self.get(meta['id'])['sources']}
                for hit in self.retrievers[meta['id']].search(' '.join(terms),limit=limit):
                    s=lookup.get(hit['source']['id'].replace(meta['id']+'_',meta['id']+'-',1))
                    if s:structural.append({**s,'document_name':meta['name'],'metadata':meta,
                        'selection_relevance':hit['score'],'retrieval_mode':hit['mode']})
            mixed=[]
            for i in range(max(len(original),len(structural))):
                if i<len(structural):mixed.append(structural[i])
                if i<len(original):mixed.append(original[i])
            groups[meta['id']]=mixed
        chosen=[];seen=set();used=0
        def add(s):
            nonlocal used
            if s['id'] in seen:return True
            if used+len(s['text'])>budget or len(chosen)>=limit:return False
            chosen.append(s);seen.add(s['id']);used+=len(s['text']);return True
        for meta in manifest:
            if meta['required'] and not any(add(s) for s in groups[meta['id']]):
                raise DocumentError('필수 자료를 담기에 분석 용량이 부족합니다.')
        for meta in sorted(manifest,key=lambda m:-PRIORITIES[m['priority']]):
            for s in groups[meta['id']]:add(s)
        return chosen

    def __getattr__(self,name):return getattr(self.original,name)

    def crop(self,key,region):return self.keyword.crop(key,region)
