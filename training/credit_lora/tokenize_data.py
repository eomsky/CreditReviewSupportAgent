"""Assistant-only, no-truncation tokenization with deterministic stratification."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random

BASE='google/gemma-4-26B-A4B-it'
REVISION='4d7ae4984b7db7de8f8457170b3f1a419ee76d52'
STAGES=['factor_style','bundle','section','full_report']

def encode_record(tokenizer, record, max_length):
    messages=record['messages']
    prompt=tokenizer.apply_chat_template(messages[:-1],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    full=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=False,enable_thinking=False)
    if not full.startswith(prompt):
        raise ValueError('Assistant prefix differs from generation template; refusing incorrect loss mask')
    encoding=tokenizer(full,add_special_tokens=False,return_offsets_mapping=True)
    ids=encoding['input_ids']
    if len(ids)>max_length: return None,{'reason':'overlength','tokens':len(ids)}
    # Mask a token if it includes any prompt characters; avoid boundary leakage.
    labels=[token if end>len(prompt) and start>=len(prompt) else -100
            for token,(start,end) in zip(ids,encoding['offset_mapping'])]
    if not any(x!=-100 for x in labels): raise ValueError('No assistant tokens')
    return {'input_ids':ids,'attention_mask':[1]*len(ids),'labels':labels,
            'record_id':record['record_id'],'case_id':record['case_id'],
            'archetype_id':record['archetype_id'],'stage':record['stage']},None

def stratified(rows, count, seed):
    groups=defaultdict(list)
    for r in rows: groups[r['archetype_id']].append(r)
    rng=random.Random(seed)
    for g in groups.values(): rng.shuffle(g)
    order=list(groups); rng.shuffle(order); selected=[]
    while len(selected)<count and any(groups.values()):
        for g in order:
            if groups[g] and len(selected)<count: selected.append(groups[g].pop())
    return selected

def main():
    from transformers import AutoTokenizer
    p=argparse.ArgumentParser(); p.add_argument('data',type=Path); p.add_argument('output',type=Path)
    p.add_argument('--max-length',type=int,default=6144)
    p.add_argument('--counts',default='384,240,160,64'); a=p.parse_args()
    tokenizer=AutoTokenizer.from_pretrained(BASE,revision=REVISION,local_files_only=True)
    a.output.mkdir(parents=True,exist_ok=True); audit=[]; counts={}; selection={}
    limits=dict(zip(STAGES,map(int,a.counts.split(','))))
    for stage in STAGES:
        for split in ['train','validation','test']:
            raw=[json.loads(s) for s in (a.data/f'{stage}_{split}.jsonl').read_text().splitlines()]
            valid=[]
            for r in raw:
                item,error=encode_record(tokenizer,r,a.max_length)
                if error: audit.append({'record_id':r['record_id'],'split':split,**error})
                else: valid.append(item)
            selected=stratified(valid,limits[stage] if split=='train' else 12,42)
            path=a.output/f'{stage}_{split}.jsonl'
            path.write_text(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in selected))
            lens=[len(x['input_ids']) for x in selected]
            counts[stage+'_'+split]={'available':len(valid),'selected':len(selected),
                'tokens':sum(lens),'max_tokens':max(lens,default=0),
                'assistant_tokens':sum(sum(v!=-100 for v in x['labels']) for x in selected)}
            selection[stage+'_'+split]=[x['record_id'] for x in selected]
    manifest={'base_model':BASE,'revision':REVISION,'max_length':a.max_length,'counts':counts,
        'excluded_overlength':len(audit),'truncation':False,'loss':'assistant tokens only',
        'source_manifest_sha256':hashlib.sha256((a.data/'manifest.json').read_bytes()).hexdigest(),
        'selection':selection,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.output.glob('*.jsonl')}}
    (a.output/'tokenization_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (a.output/'overlength.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in audit))
    print(json.dumps(counts,indent=2)); print('OVERLENGTH',len(audit),flush=True)

if __name__=='__main__': main()
