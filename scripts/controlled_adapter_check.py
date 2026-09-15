"""Read-only contract checks on the controlled input adapter and actual artifacts."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'scripts')]
from frozen_structured_sources import StructuredStore
from review_documents import DocumentStore


def main():
    artifacts={json.loads(p.read_text())['pdf_sha256']:p.parent for p in (ROOT/'outputs/frozen_candidates').glob('structured-*-probe/timings.json')}
    original=DocumentStore(ROOT/'workspace/review_documents')
    store=StructuredStore(original,artifacts)
    seen=set();count=0
    for digest,folder in artifacts.items():
        raw=json.loads((folder/'chunks.json').read_text(encoding='utf-8'))
        expected={digest+'-spt017_'+c['chunk_id']:json.loads(c['document']) for c in raw}
        actual=store.get(digest)['sources']
        assert {s['id'] for s in actual}==set(expected), 'Missing or extra SPT sources'
        for s in actual:
            assert s['id'] not in seen,'Source ID collision'
            seen.add(s['id']);count+=1
            assert s['structured']==expected[s['id']], 'Structured cells changed'
            assert s['bbox'][2]>s['bbox'][0] and s['bbox'][3]>s['bbox'][1], 'Invalid image bounds'
    payload=json.loads((ROOT/'outputs/experiments/20260914/frozen/baseline_run/input.json').read_text(encoding='utf-8'))['payload']
    manifest=store.manifest(payload['documents'])
    for meta in manifest:
        if meta['id'] not in artifacts:assert store.get(meta['id'])==original.get(meta['id'])
    required={m['id'] for m in manifest if m['required']}
    for terms in [['현금흐름','기말'],['종속기업','지분율'],['매출','수익성']]:
        selected=store.select(terms,manifest,budget=16000,limit=12)
        assert required<={s['document_id'] for s in selected}
        assert sum(len(s['text']) for s in selected)<=16000
    sample=next(s for d in store.documents.values() for s in d['sources'] if 'P0013_T001' in s['id'] and s['page']==13)
    image=store.crop(sample['document_id'],sample['id'][len(sample['document_id'])+1:])
    assert image.startswith(b'\x89PNG'), 'Image retrieval failed'
    out=ROOT/'outputs/frozen_candidates/controlled-comparison'
    (out/'continuation-source.png').write_bytes(image)
    result={'structural_sources_checked':count,'structured_json_exact':True,'source_ids_unique':True,'non_pdf_unchanged':True,'required_documents_present':True,'budget_preserved':True,'continuation_image_page':sample['page'],'end_to_end':False}
    (out/'adapter-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
