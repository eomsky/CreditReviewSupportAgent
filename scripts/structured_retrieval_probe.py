"""Compare current substring search and the existing structural sparse retriever."""
import json
import sys
from pathlib import Path
from datetime import date
from types import SimpleNamespace
from time import perf_counter

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
sys.path.insert(0,str(ROOT/'scripts'))
from credit_review.documents import sources_from_spt
from credit_review.retrieval import Retriever
from review_documents import DocumentStore


def main():
    folder=ROOT/'outputs/frozen_candidates/structured-pdf-probe'
    master=json.loads((folder/'MASTER.json').read_text(encoding='utf-8'))
    chunks=[SimpleNamespace(**c) for c in json.loads((folder/'chunks.json').read_text(encoding='utf-8'))]
    digest=json.loads((folder/'timings.json').read_text())['pdf_sha256']
    # Same single-document corpus. Timestamp is test ingestion time, not publication evidence.
    rows=sources_from_spt(master,chunks,digest,date.today())
    start=perf_counter();retriever=Retriever(rows,date.today());index_seconds=perf_counter()-start
    store=DocumentStore(ROOT/'workspace/review_documents')
    manifest=[{'id':digest,'name':store.get(digest)['name'],'description':'','priority':'매우 중요','required':True}]
    queries=['영업활동 투자활동 재무활동 기말 현금흐름','종속기업 소재지 지분율 사업내용',
             '차입금 사채 만기 상환 유동성','금융비용 이자비용 법인세비용']
    results=[]
    for query in queries:
        start=perf_counter();old=store.select(query.split(),manifest,budget=16000,limit=12);old_time=perf_counter()-start
        start=perf_counter();new=retriever.search(query,limit=12);new_time=perf_counter()-start
        results.append({'query':query,'substring_seconds':old_time,'sparse_seconds':new_time,
            'substring_hits':[{'id':s['id'],'page':s['page']} for s in old],
            'sparse_hits':[{'id':s['source']['id'],'page':s['source']['page'],
              'table':s['source']['metadata'].get('physical_table_id'),'score':s['score']} for s in new]})
    output={'scope':'Single PDF retrieval-only comparison, no dense embedding or end-to-end generation.',
        'mode':retriever.mode,'index_seconds':index_seconds,'queries':results}
    out=ROOT/'outputs/frozen_candidates/retrieval-probe';out.mkdir(exist_ok=True)
    (out/'result.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(output,ensure_ascii=False))


if __name__=='__main__':main()
