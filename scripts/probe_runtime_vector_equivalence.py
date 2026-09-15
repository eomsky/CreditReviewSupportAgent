"""Compare generic upload adapter against frozen retrieval using the same sources."""
import json,time
from pathlib import Path
from review_documents import DocumentStore
from runtime_vector_store import RuntimePageStore
ROOT=Path(__file__).resolve().parents[1]
frozen=ROOT/'outputs/experiments/20260914/frozen'
uploads=json.loads((frozen/'baseline_run/input.json').read_text(encoding='utf-8'))['payload']['documents']
baseline=json.loads((ROOT/'outputs/frozen_candidates/controlled-comparison/page-retrieval-probe.json').read_text(encoding='utf-8'))['queries']
store=RuntimePageStore(DocumentStore(ROOT/'workspace/review_documents'),ROOT/'outputs/frozen_candidates/runtime-equivalence-index')
started=time.monotonic();results={}
try:
    for name,terms,budget,limit in [('cashflow',['연결현금흐름표','영업활동','투자활동','재무활동','기말현금'],16000,24),('subsidiaries',['연결대상종속회사','종속기업의현황','주요종속','소재지'],4500,3),('income',['연결손익계산서','연결포괄손익계산서','당기순이익'],4500,4)]:
        hits=store.select(terms,store.manifest(uploads),budget,limit)
        expected=baseline[name]['sources']
        actual=[{'id':s['id'],'page':s.get('page'),'text':s['text']} for s in hits]
        results[name]={'exact_same_sources_order_and_text':actual==expected,'count':len(actual)}
    result={'end_to_end':False,'elapsed_seconds':time.monotonic()-started,'indexing':store.vector.metrics,'queries':results}
    (ROOT/'outputs/frozen_candidates/runtime-equivalence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    assert all(r['exact_same_sources_order_and_text'] for r in results.values())
finally:store.vector.client.close()
