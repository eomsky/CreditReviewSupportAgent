"""Same-prompt base/adapter comparison on held-out archetypes, with time caps."""
import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import time
from tokenize_data import BASE, REVISION, STAGES, stratified
from prepare_data import unsupported_numbers

def main():
    p=argparse.ArgumentParser(); p.add_argument('data',type=Path); p.add_argument('adapter',type=Path)
    p.add_argument('output',type=Path); p.add_argument('--per-stage',type=int,default=2)
    p.add_argument('--max-seconds',type=float,default=90); p.add_argument('--max-new-tokens',type=int,default=2300)
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    import torch
    from transformers import Gemma4ForConditionalGeneration,AutoTokenizer,set_seed
    from peft import PeftModel
    set_seed(42)
    tokenizer=AutoTokenizer.from_pretrained(BASE,revision=REVISION,local_files_only=True)
    base=Gemma4ForConditionalGeneration.from_pretrained(BASE,revision=REVISION,local_files_only=True,
        dtype=torch.bfloat16,device_map={'':0},attn_implementation='sdpa')
    model=PeftModel.from_pretrained(base,a.adapter,is_trainable=False)
    model.eval(); model.config.use_cache=True
    if hasattr(model,'gradient_checkpointing_disable'): model.gradient_checkpointing_disable()
    rows=[]
    for stage in STAGES:
        source=[json.loads(s) for s in (a.data/f'{stage}_test.jsonl').read_text().splitlines()]
        rows.extend(stratified(source,a.per_stage,97))
    results=[]
    for row in rows:
        messages=row['messages'][:-1]
        prompt=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
        inputs=tokenizer(prompt,return_tensors='pt',add_special_tokens=False).to('cuda')
        for mode in ['base','adapter']:
            started=time.monotonic()
            try:
                with (model.disable_adapter() if mode=='base' else nullcontext()),torch.inference_mode():
                    output=model.generate(**inputs,do_sample=False,max_new_tokens=a.max_new_tokens,
                        max_time=a.max_seconds,use_cache=True,pad_token_id=tokenizer.pad_token_id)
                new=output[0,inputs['input_ids'].shape[1]:]
                text=tokenizer.decode(new,skip_special_tokens=True).strip()
                seconds=time.monotonic()-started
                expected=[]; observed=[]; parsed=None
                if row['stage'] in {'factor_style','bundle'} and row['messages'][-1]['content'].startswith('{'):
                    target=json.loads(row['messages'][-1]['content']); expected=[x['factor_id'] for x in target['findings']]
                    try:
                        parsed=json.loads(text)
                        observed=[x['factor_id'] for x in parsed.get('findings',[])]
                    except (ValueError,TypeError,KeyError): pass
                unknown=unsupported_numbers(row['messages'][:-1],text)
                result={'record_id':row['record_id'],'stage':row['stage'],'archetype_id':row['archetype_id'],
                    'mode':mode,'seconds':seconds,'input_tokens':inputs['input_ids'].shape[1],
                    'output_tokens':len(new),'tokens_per_second':len(new)/max(seconds,.001),
                    'time_limit_reached':seconds>=a.max_seconds,'token_limit_reached':len(new)>=a.max_new_tokens,
                    'expected_factors':expected,'observed_factors':observed,
                    'factor_recall':len(set(expected)&set(observed))/len(expected) if expected else None,
                    'factor_duplicates':len(observed)!=len(set(observed)),
                    'json_valid':parsed is not None if expected else None,
                    'unsupported_numeric_candidates':unknown,'text':text,
                    'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()}
            except Exception as exc:
                result={'record_id':row['record_id'],'mode':mode,'stage':row['stage'],'error':type(exc).__name__+': '+str(exc),
                        'seconds':time.monotonic()-started}
                torch.cuda.empty_cache()
            results.append(result)
            with (a.output/'comparisons.jsonl').open('a') as f: f.write(json.dumps(result,ensure_ascii=False)+'\n')
            print('EVAL',json.dumps({k:v for k,v in result.items() if k!='text'}),flush=True)
    summary={'base':BASE,'revision':REVISION,'adapter':str(a.adapter),'pairs':len(rows),
       'same_prompts':True,'held_out_split':'test','expert_quality_pass':None,
       'note':'Numeric candidates are screening flags, not proven errors; human/source review is required.',
       'modes':{}}
    for mode in ['base','adapter']:
        subset=[r for r in results if r['mode']==mode]
        recalls=[r['factor_recall'] for r in subset if r.get('factor_recall') is not None]
        summary['modes'][mode]={'completed':sum('text' in r for r in subset),
          'total_seconds':sum(r['seconds'] for r in subset),
          'mean_factor_recall':sum(recalls)/len(recalls) if recalls else None,
          'numeric_flagged_records':sum(bool(r.get('unsupported_numeric_candidates')) for r in subset),
          'timeouts':sum(r.get('time_limit_reached',False) for r in subset)}
    (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print('EVAL_COMPLETE',json.dumps(summary),flush=True)

if __name__=='__main__': main()
