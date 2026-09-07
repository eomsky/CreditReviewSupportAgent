"""Bounded four-stage SFT with detachable adapters and resumable checkpoints."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import zipfile

BASE='google/gemma-4-26B-A4B-it'
REVISION='4d7ae4984b7db7de8f8457170b3f1a419ee76d52'
STAGES=['factor_style','bundle','section','full_report']

def atomic(path, data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2))
    os.replace(tmp,path)

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''): h.update(block)
    return h.hexdigest()

def package(path, target):
    """Only complete checkpoint trees are published. Base weights never saved."""
    path=Path(path); target=Path(target); target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix('.zip.tmp')
    files=[p for p in path.rglob('*') if p.is_file()]
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_STORED) as z:
        for p in files: z.write(p,str(p.relative_to(path.parent)))
    os.replace(tmp,target)
    atomic(target.with_suffix('.manifest.json'),{'path':str(target),'bytes':target.stat().st_size,
        'sha256':sha(target),'files':len(files),'created_at':datetime.now(timezone.utc).isoformat()})

def main():
    p=argparse.ArgumentParser(); p.add_argument('data',type=Path); p.add_argument('run',type=Path)
    p.add_argument('--deadline',default='2026-09-07T21:05:00+00:00')
    p.add_argument('--stage-seconds',default='2100,3300,2400,1800')
    p.add_argument('--stage',choices=STAGES+['refinement']); p.add_argument('--resume',default=None)
    p.add_argument('--adapter',default=None); p.add_argument('--quantize',action='store_true')
    p.add_argument('--max-steps',type=int,default=192); p.add_argument('--rank',type=int,default=16)
    p.add_argument('--gradient-accumulation',type=int,default=4)
    p.add_argument('--learning-rate',type=float,default=2e-5)
    p.add_argument('--checkpoint-steps',type=int,default=4)
    p.add_argument('--stop-after-resumed-steps',type=int,
                   help='Recovery smoke test: stop after N additional steps without changing the original LR schedule')
    a=p.parse_args(); a.run.mkdir(parents=True,exist_ok=True)
    if a.stop_after_resumed_steps is not None and (not a.resume or not a.stage or a.stop_after_resumed_steps<1):
        p.error('--stop-after-resumed-steps requires --resume, --stage and a positive value')
    os.environ['TOKENIZERS_PARALLELISM']='false'
    os.environ['WANDB_DISABLED']='true'
    import torch
    from torch.utils.data import Dataset
    from transformers import Gemma4ForConditionalGeneration, AutoTokenizer, TrainingArguments, Trainer, TrainerCallback, BitsAndBytesConfig, set_seed
    from peft import LoraConfig, get_peft_model, PeftModel, prepare_model_for_kbit_training
    set_seed(42)
    deadline=datetime.fromisoformat(a.deadline).timestamp()
    if time.time()>=deadline: raise RuntimeError('Training deadline has elapsed')
    durations=dict(zip(STAGES,map(int,a.stage_seconds.split(','))))
    durations['refinement']=600  # A short, separately evaluated rehearsal trial.
    manifest={'base_model':BASE,'base_revision':REVISION,'tokenizer_revision':REVISION,
       'started_at':datetime.now(timezone.utc).isoformat(),'deadline':a.deadline,
       'arguments':{k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
       'data_manifest_sha256':sha(a.data/'tokenization_manifest.json'),
       'software':{x:importlib.metadata.version(x) for x in ['torch','transformers','peft','accelerate','bitsandbytes']},
       'gpu':torch.cuda.get_device_name(0),'gpu_memory_bytes':torch.cuda.get_device_properties(0).total_memory,
       'git_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
       'base_merged':False,'stages':{}}
    atomic(a.run/'run_manifest.json',manifest)
    kwargs={'revision':REVISION,'local_files_only':True,'dtype':torch.bfloat16,
            'device_map':{'':0},'attn_implementation':'sdpa','low_cpu_mem_usage':True}
    if a.quantize:
        kwargs['quantization_config']=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
            bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_storage=torch.bfloat16)
    print('MODEL_LOADING',flush=True)
    model=Gemma4ForConditionalGeneration.from_pretrained(BASE,**kwargs)
    model.config.use_cache=False
    if a.quantize: model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    target_modules=[name for name,module in model.named_modules()
                    if '.self_attn.' in name and name.rsplit('.',1)[-1] in {'q_proj','k_proj','v_proj','o_proj'}
                    and 'vision' not in name and 'audio' not in name]
    if not target_modules: raise RuntimeError('No language attention modules matched')
    if a.adapter:
        model=PeftModel.from_pretrained(model,a.adapter,is_trainable=True)
    else:
        model=get_peft_model(model,LoraConfig(r=a.rank,lora_alpha=a.rank*2,lora_dropout=.05,
            bias='none',task_type='CAUSAL_LM',target_modules=target_modules))
    model.enable_input_require_grads()
    tokenizer=AutoTokenizer.from_pretrained(BASE,revision=REVISION,local_files_only=True)
    tokenizer.padding_side='right'
    if tokenizer.pad_token_id is None: tokenizer.pad_token=tokenizer.eos_token
    manifest['target_modules']=target_modules
    manifest['trainable_parameters']=sum(p.numel() for p in model.parameters() if p.requires_grad)
    manifest['total_parameters']=sum(p.numel() for p in model.parameters())
    atomic(a.run/'run_manifest.json',manifest)
    print('MODEL_READY',json.dumps({'trainable':manifest['trainable_parameters'],'targets':len(target_modules),
         'allocated_gib':torch.cuda.memory_allocated()/1024**3}),flush=True)

    class Rows(Dataset):
        def __init__(self,path): self.rows=[json.loads(s) for s in Path(path).read_text().splitlines()]
        def __len__(self): return len(self.rows)
        def __getitem__(self,i): return {k:self.rows[i][k] for k in ['input_ids','attention_mask','labels']}

    def collate(rows):
        n=max(len(x['input_ids']) for x in rows); n=((n+7)//8)*8
        return {k:torch.tensor([r[k]+[tokenizer.pad_token_id if k=='input_ids' else -100 if k=='labels' else 0]*(n-len(r[k])) for r in rows])
                for k in ['input_ids','attention_mask','labels']}

    stop_requested=False
    def request_stop(signum, frame):
        nonlocal stop_requested
        stop_requested=True
    signal.signal(signal.SIGTERM,request_stop)
    signal.signal(signal.SIGINT,request_stop)

    class Progress(TrainerCallback):
        def __init__(self,stage,stage_deadline):
            self.stage=stage; self.deadline=stage_deadline; self.started=time.time(); self.last_progress=time.time()
            self.resume_start=None
        def on_train_begin(self,args,state,control,**kwargs):
            self.resume_start=state.global_step
            if a.stop_after_resumed_steps is not None:
                print('RECOVERY_START',state.global_step,'additional_steps',a.stop_after_resumed_steps,flush=True)
        def on_log(self,args,state,control,logs=None,**kwargs):
            record={'stage':self.stage,'step':state.global_step,'seconds':round(time.time()-self.started,2),
                    'time':datetime.now(timezone.utc).isoformat(),'logs':logs or {},
                    'gpu_allocated_gib':round(torch.cuda.memory_allocated()/1024**3,2)}
            with (a.run/'metrics.jsonl').open('a') as f: f.write(json.dumps(record)+'\n')
            atomic(a.run/'progress.json',record)
            print('PROGRESS',json.dumps(record),flush=True)
        def on_step_end(self,args,state,control,**kwargs):
            self.last_progress=time.time()
            recovered_enough=(a.stop_after_resumed_steps is not None and self.resume_start is not None
                              and state.global_step>=self.resume_start+a.stop_after_resumed_steps)
            if stop_requested or time.time()>=self.deadline or time.time()>=deadline or recovered_enough:
                control.should_training_stop=True; control.should_save=True
            return control
        def on_save(self,args,state,control,**kwargs):
            folder=Path(args.output_dir)/f'checkpoint-{state.global_step}'
            atomic(folder/'COMPLETE.json',{'stage':self.stage,'step':state.global_step,
                'base_revision':REVISION,'created_at':datetime.now(timezone.utc).isoformat()})
            archive=a.run/'backup_queue'/f'{self.stage}-checkpoint-{state.global_step}.zip'
            package(folder,archive)
            print('BACKUP_READY',archive,flush=True)
            return control

    for stage in ([a.stage] if a.stage else STAGES):
        if stop_requested or time.time()>=deadline: break
        stage_dir=a.run/stage; stage_dir.mkdir(exist_ok=True)
        train=Rows(a.data/f'{stage}_train.jsonl'); validation=Rows(a.data/f'{stage}_validation.jsonl')
        if not len(train) or not len(validation): raise RuntimeError(f'Empty {stage} split')
        remaining=deadline-time.time()
        stage_deadline=min(deadline,time.time()+durations[stage])
        steps=min(a.max_steps,max(1,(len(train)+a.gradient_accumulation-1)//a.gradient_accumulation*2))
        callback=Progress(stage,stage_deadline)
        args=TrainingArguments(output_dir=str(stage_dir),per_device_train_batch_size=1,
            per_device_eval_batch_size=1,gradient_accumulation_steps=a.gradient_accumulation,
            learning_rate=a.learning_rate,weight_decay=.01,warmup_steps=max(1,round(steps*.03)),max_steps=steps,
            bf16=True,tf32=True,gradient_checkpointing=True,
            gradient_checkpointing_kwargs={'use_reentrant':False},optim='adamw_torch',
            logging_steps=1,save_strategy='steps',save_steps=a.checkpoint_steps,
            eval_strategy='steps',eval_steps=a.checkpoint_steps,save_total_limit=3,
            load_best_model_at_end=True,metric_for_best_model='eval_loss',greater_is_better=False,
            dataloader_num_workers=0,remove_unused_columns=False,report_to=[],
            disable_tqdm=True,seed=42,data_seed=42,max_grad_norm=1.0,
            eval_accumulation_steps=1,prediction_loss_only=True)
        trainer=Trainer(model=model,args=args,train_dataset=train,eval_dataset=validation,
                        data_collator=collate,processing_class=tokenizer,callbacks=[callback])
        print('STAGE_START',stage,'samples',len(train),'steps',steps,'deadline',stage_deadline,flush=True)
        result=trainer.train(resume_from_checkpoint=a.resume if a.stage==stage else None)
        best=stage_dir/'best_adapter'; model.save_pretrained(best,safe_serialization=True)
        tokenizer.save_pretrained(best)
        atomic(best/'adapter_manifest.json',{'stage':stage,'base_model':BASE,'base_revision':REVISION,
            'global_step':trainer.state.global_step,'best_checkpoint':trainer.state.best_model_checkpoint,
            'best_validation_loss':trainer.state.best_metric,'train_metrics':result.metrics,'merged':False})
        package(best,a.run/'backup_queue'/f'{stage}-best-adapter.zip')
        manifest['stages'][stage]={'adapter':str(best),'steps':trainer.state.global_step,
            'planned_steps':steps,'recovery_start_step':callback.resume_start if a.resume else None,
            'best_validation_loss':trainer.state.best_metric,'metrics':result.metrics,
            'finished_at':datetime.now(timezone.utc).isoformat()}
        atomic(a.run/'run_manifest.json',manifest)
        print('STAGE_COMPLETE',stage,json.dumps(manifest['stages'][stage]),flush=True)
        del trainer
        import gc; gc.collect(); torch.cuda.empty_cache()
    manifest['finished_at']=datetime.now(timezone.utc).isoformat()
    all_stages=len(manifest['stages'])==len([a.stage] if a.stage else STAGES)
    if a.stop_after_resumed_steps is not None:
        recovered=manifest['stages'].get(a.stage,{})
        enough=recovered.get('steps',0)-int(recovered.get('recovery_start_step') or 0)>=a.stop_after_resumed_steps
        manifest['status']='RECOVERY_SMOKE_COMPLETE' if enough else 'RECOVERY_SMOKE_INCOMPLETE'
    else:
        all_steps=all(x['steps']>=x['planned_steps'] for x in manifest['stages'].values())
        manifest['status']='COMPLETE' if all_stages and all_steps else 'STOPPED_EARLY'
    atomic(a.run/'run_manifest.json',manifest)
    print('TRAINING_END',manifest['status'],flush=True)

if __name__=='__main__': main()
