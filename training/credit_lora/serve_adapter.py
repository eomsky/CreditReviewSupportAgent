"""Restore the saved inference command, optionally exposing unmerged LoRA models."""
import argparse
import json
from pathlib import Path
import socket
import subprocess

from tokenize_data import BASE, REVISION


def compact_structured_command(command):
    command=list(command)
    flag='--structured-outputs-config'
    if flag in command:
        index=command.index(flag)+1
        config=json.loads(command[index])
        config.update(backend='xgrammar',disable_any_whitespace=True)
        command[index]=json.dumps(config)
    else:
        command.extend([flag,json.dumps({'backend':'xgrammar','disable_any_whitespace':True})])
    return command


def adapter_arguments(adapters):
    specs=[]; names=set()
    for item in adapters:
        name, path = item.split('=',1)
        if not name or name in names or name==BASE:
            raise ValueError('Adapter names must be distinct from the base model')
        names.add(name); folder=Path(path).resolve()
        config=json.loads((folder/'adapter_config.json').read_text())
        manifest=json.loads((folder/'adapter_manifest.json').read_text())
        if config.get('base_model_name_or_path')!=BASE or manifest.get('base_revision')!=REVISION:
            raise ValueError('Adapter/base revision mismatch')
        if manifest.get('merged') is not False or not (folder/'adapter_model.safetensors').is_file():
            raise ValueError('A complete unmerged adapter is required')
        if config.get('r')!=16:
            raise ValueError('This serving configuration expects rank 16')
        specs.append(json.dumps({'name':name,'path':str(folder),'base_model_name':BASE}))
    if not specs: return []
    return ['--enable-lora','--max-lora-rank','16','--max-loras',str(min(4,len(specs))),
            '--max-cpu-loras',str(max(4,len(specs))),'--lora-modules',*specs]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--restore-args',type=Path,default=Path('/content/credit_llm_server/restore_args.json'))
    parser.add_argument('--adapter',action='append',default=[],help='served-name=/absolute/adapter/path')
    parser.add_argument('--output',type=Path,default=Path('/content/credit_llm_server'))
    args=parser.parse_args()
    command=json.loads(args.restore_args.read_text())
    if not isinstance(command,list) or not all(isinstance(x,str) for x in command):
        raise ValueError('Saved inference command must be a string list')
    if '--enable-lora' in command or '--lora-modules' in command:
        raise ValueError('Restore file must contain the base-only command')
    host=command[command.index('--host')+1] if '--host' in command else '127.0.0.1'
    port=int(command[command.index('--port')+1]) if '--port' in command else 8000
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex((host,port))==0:
            raise RuntimeError('Inference port is already occupied; stop the intended server explicitly')
    command=compact_structured_command(command)
    command.extend(adapter_arguments(args.adapter))
    args.output.mkdir(parents=True,exist_ok=True)
    log=args.output/'vllm_restored.log'
    with log.open('w') as handle:
        process=subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
    status={'pid':process.pid,'log':str(log),'base_model':BASE,
            'adapter_names':[x.split('=',1)[0] for x in args.adapter],
            'state':'STARTING','base_merged':False}
    (args.output/'restored_process.json').write_text(json.dumps(status,indent=2))
    print(json.dumps(status))


if __name__=='__main__': main()
