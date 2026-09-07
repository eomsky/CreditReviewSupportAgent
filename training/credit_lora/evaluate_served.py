"""Paired streamed evaluation against already served base/LoRA models.

No GPU model reload, weight merge, training, or source-data mutation is performed.
Private connection files supply authentication; keys are never included in outputs.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import re
import time

import httpx
from tokenize_data import STAGES, stratified
from prepare_data import unsupported_numbers


def assess(row, text):
    expected=[]; observed=[]; parsed=None; parse_error=None
    target=row['messages'][-1]['content']
    if row['stage'] in {'factor_style','bundle'} and target.startswith('{'):
        expected=[x['factor_id'] for x in json.loads(target)['findings']]
        try:
            parsed=json.loads(text)
            if not isinstance(parsed,dict) or not isinstance(parsed.get('findings'),list):
                raise ValueError('Expected findings object')
            observed=[x['factor_id'] for x in parsed['findings']]
            if not all(isinstance(x,str) for x in observed):
                raise ValueError('Factor IDs must be strings')
        except (ValueError,TypeError,KeyError) as exc:
            parsed=None; observed=[]; parse_error=type(exc).__name__
    try: source=json.loads(row['messages'][-2]['content'])
    except (ValueError,TypeError): source={}
    bad=[]
    if parsed:
        for finding in parsed['findings']:
            judgement=finding.get('judgement',{})
            if not isinstance(judgement,dict): continue
            for field,collection in [('evidence_ids','sources'),('calculation_ids','calculations')]:
                refs=judgement.get(field,[])
                if not isinstance(refs,list):
                    bad.append(field+':invalid_type'); continue
                bad.extend(str(x) for x in refs if str(x) not in source.get(collection,{}))
    return {'expected_factors':expected,'observed_factors':observed,
            'json_valid':parsed is not None if expected else None,
            'parse_error':parse_error,
            'factor_set_exact':sorted(expected)==sorted(observed) if expected else None,
            'factor_duplicates':len(observed)!=len(set(observed)),
            'invalid_reference_ids':bad,
            'unsupported_numeric_candidates':unsupported_numbers(row['messages'][:-1],text),
            'heading_count':len(re.findall(r'^#{1,6}\s',text,re.M))}


async def generate(client, url, model, messages, seconds, tokens):
    started=time.monotonic(); pieces=[]; first=None; usage={}; finish=None; error=None
    try:
        # An absolute deadline includes connection, prefill, and all streamed tokens.
        async with asyncio.timeout(seconds):
            async with client.stream('POST',url+'/chat/completions',json={
                'model':model,'messages':messages,'temperature':0,'seed':42,
                'max_tokens':tokens,'stream':True,'stream_options':{'include_usage':True},
                'chat_template_kwargs':{'enable_thinking':False}}) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith('data:'): continue
                    payload=line[5:].strip()
                    if payload=='[DONE]': break
                    event=json.loads(payload)
                    if event.get('error'): raise RuntimeError('Server returned a stream error')
                    if event.get('usage'): usage=event['usage']
                    for choice in event.get('choices',[]):
                        if choice.get('finish_reason'): finish=choice['finish_reason']
                        content=choice.get('delta',{}).get('content')
                        if content:
                            if first is None: first=time.monotonic()-started
                            pieces.append(content)
                if finish is None: error='IncompleteStream'
    except TimeoutError: error='AbsoluteTimeout'
    except httpx.HTTPStatusError as exc: error='HTTP_'+str(exc.response.status_code)
    except Exception as exc: error=type(exc).__name__
    return {'text':''.join(pieces),'seconds':time.monotonic()-started,
            'first_text_seconds':first,'finish_reason':finish,'usage':usage,'error':error,
            'complete':error is None and finish=='stop'}


async def run(args):
    config=json.loads(args.connection.read_text(encoding='utf-8'))
    url=config['base_url'].rstrip('/')
    headers={'Authorization':'Bearer '+config['api_key']} if config.get('api_key') else {}
    args.output.mkdir(parents=True,exist_ok=True)
    result_path=args.output/'comparisons.jsonl'
    if result_path.exists(): raise FileExistsError('Use a new evaluation output directory')
    rows=[]
    for stage in STAGES:
        if args.stage and stage not in args.stage: continue
        source=[json.loads(s) for s in (args.data/f'{stage}_{args.split}.jsonl').read_text().splitlines()]
        rows.extend(stratified(source,args.per_stage,97))
    if args.probe_file:
        probes=[json.loads(s) for s in args.probe_file.read_text().splitlines()]
        if any(r.get('train_allowed') is not False for r in probes):
            raise ValueError('Probe records must prohibit training')
        rows.extend(probes)
    models=list(dict.fromkeys(args.model))
    if len(models)<2: raise ValueError('At least two distinct served models are required')
    async with httpx.AsyncClient(headers=headers,timeout=None) as client:
        async with asyncio.timeout(20):
            response=await client.get(url+'/models'); response.raise_for_status()
        available={x['id'] for x in response.json()['data']}
        if set(models)-available: raise ValueError('One or more requested models are not served')
        warmups={}
        for model in models:
            warmups[model]=await generate(client,url,model,[{'role':'user','content':'준비 완료라고만 답하세요.'}],60,32)
        results=[]
        for index,row in enumerate(rows):
            messages=row['messages'][:-1]
            prompt_hash=hashlib.sha256(json.dumps(messages,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            order=models[index%len(models):]+models[:index%len(models)]
            for model in order:
                reply=await generate(client,url,model,messages,args.max_seconds,args.max_new_tokens)
                record={'record_id':row['record_id'],'archetype_id':row['archetype_id'],
                        'stage':row['stage'],'model':model,'prompt_sha256':prompt_hash,
                        'evaluation_criteria':row.get('evaluation_criteria'),
                        **reply,**assess(row,reply['text'])}
                results.append(record)
                with result_path.open('a',encoding='utf-8') as handle:
                    handle.write(json.dumps(record,ensure_ascii=False)+'\n')
                print('SERVED_EVAL',json.dumps({k:v for k,v in record.items()
                      if k not in {'text','evaluation_criteria'}},ensure_ascii=False),flush=True)
    summary={'split':args.split,'pairs':len(rows),'models':models,'same_messages':True,
             'balanced_order':True,'warmup_excluded':True,'max_seconds':args.max_seconds,
             'max_new_tokens':args.max_new_tokens,'warmups':warmups,'expert_quality_pass':None,
             'note':'Reference and numeric checks are screening signals, not expert quality approval.',
             'results':{}}
    for model in models:
        subset=[r for r in results if r['model']==model]
        summary['results'][model]={'completed':sum(r['complete'] for r in subset),
            'calls':len(subset),'seconds':sum(r['seconds'] for r in subset),
            'exact_factor_sets':sum(r['factor_set_exact'] is True for r in subset),
            'invalid_reference_records':sum(bool(r['invalid_reference_ids']) for r in subset),
            'numeric_flagged_records':sum(bool(r['unsupported_numeric_candidates']) for r in subset)}
    (args.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SERVED_EVAL_COMPLETE',json.dumps(summary['results']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('data',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('--connection',type=Path,required=True)
    parser.add_argument('--model',action='append',required=True)
    parser.add_argument('--split',choices=['validation','test'],default='validation')
    parser.add_argument('--stage',action='append',choices=STAGES)
    parser.add_argument('--per-stage',type=int,default=1)
    parser.add_argument('--probe-file',type=Path)
    parser.add_argument('--max-seconds',type=float,default=90)
    parser.add_argument('--max-new-tokens',type=int,default=6000)
    asyncio.run(run(parser.parse_args()))
