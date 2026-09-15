"""Read-only retrieval probe; no generation calls or production modifications."""
import json
from pathlib import Path
from review_documents import DocumentStore
from frozen_page_vector_sources import PageVectorStore

ROOT = Path(__file__).resolve().parents[1]
frozen = ROOT/'outputs/experiments/20260914/frozen'
uploads = json.loads((frozen/'baseline_run/input.json').read_text(encoding='utf-8'))['payload']['documents']
store = PageVectorStore(DocumentStore(ROOT/'workspace/review_documents'), uploads, frozen,
                        ROOT/'outputs/frozen_candidates/page-vector-index')
manifest = store.manifest(uploads)
results = {}
for name, terms, budget, limit in [
    ('cashflow', ['연결현금흐름표','영업활동','투자활동','재무활동','기말현금'], 16000, 24),
    ('subsidiaries', ['연결대상종속회사','종속기업의현황','주요종속','소재지'], 4500, 3),
    ('income', ['연결손익계산서','연결포괄손익계산서','당기순이익'], 4500, 4),
]:
    hits = store.select(terms, manifest, budget, limit)
    results[name] = {'characters':sum(len(s['text']) for s in hits),
                     'sources':[{'id':s['id'],'page':s.get('page'),'text':s['text']} for s in hits]}
out = ROOT/'outputs/frozen_candidates/controlled-comparison/page-retrieval-probe.json'
out.write_text(json.dumps({'index':store.vector.info,'queries':results},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{'characters':v['characters'],'pages':[s['page'] for s in v['sources']]} for k,v in results.items()}))
store.vector.client.close()
