"""Retrieve original-case evidence for a specified report question set."""
import argparse,json,time,re
from pathlib import Path
from review_documents import DocumentStore
from runtime_vector_store import RuntimePageStore

def main():
    ap=argparse.ArgumentParser();ap.add_argument('output');ap.add_argument('--terms',nargs='+',required=True);ap.add_argument('--required',nargs='*',default=[]);a=ap.parse_args()
    root=Path(__file__).resolve().parents[1];out=Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
    uploads=json.loads((root/'outputs/experiments/20260914/frozen/baseline_run/input.json').read_text(encoding='utf-8'))['payload']['documents']
    start=time.perf_counter();store=RuntimePageStore(DocumentStore(root/'workspace/review_documents'),root/'outputs/frozen_candidates/runtime-equivalence-index')
    try:
        manifest=store.manifest(uploads);hits=[];seen=set();queries=[]
        for term in a.terms:
            began=time.perf_counter();selected=store.select([term],manifest,9000,6)
            queries.append({'query':term,'source_ids':[s['id'] for s in selected],'seconds':time.perf_counter()-began})
            for s in selected:
                key=(s.get('document_id'),s.get('page'),s['text'])
                if key not in seen:seen.add(key);hits.append(s)
        coverage=[];fallback_chars=0
        normalize=lambda text:re.sub(r'\s+','',text)
        for term in a.required:
            token=normalize(term);matches=[s['id'] for s in hits if token in normalize(s['text']) and s.get('retrieval_mode')!='required_term_fallback']
            cached_fallback=[s['id'] for s in hits if token in normalize(s['text']) and s.get('retrieval_mode')=='required_term_fallback']
            added=[];omitted=0
            if not matches and not cached_fallback:
                for meta in manifest:
                    document=store.original.get(meta['id'])
                    for raw in document['sources']:
                        if token not in normalize(raw['text']):continue
                        key=(meta['id'],raw.get('page'),raw['text'])
                        if key in seen:continue
                        if fallback_chars+len(raw['text'])>14000:omitted+=1;continue
                        s={**raw,'document_id':meta['id'],'document_name':document['name'],'retrieval_mode':'required_term_fallback','matched_term':term}
                        hits.append(s);seen.add(key);added.append(s['id']);fallback_chars+=len(s['text'])
            coverage.append({'term':term,'vector_source_ids':matches,'fallback_source_ids':cached_fallback+added,'omitted_for_budget':omitted,'found':bool(matches or cached_fallback or added)})
        result={'terms':a.terms,'queries':queries,'coverage':coverage,'sources':hits,'elapsed_seconds':time.perf_counter()-start,'index_updates':store.vector.metrics,'scope':'case originals only; per-question budget and bounded lexical fallback for missing required terms; supplied reference cases excluded'}
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'elapsed_seconds':result['elapsed_seconds'],'sources':[(s['id'],s.get('page'),s['text'][:90]) for s in hits]},ensure_ascii=False))
    finally:store.vector.client.close()

if __name__=='__main__':main()
