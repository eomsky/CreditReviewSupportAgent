"""Continue a bounded validation comparison when the identified training PID exits."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from watch_training import identity
from tokenize_data import STAGES


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('pid',type=int); parser.add_argument('run',type=Path)
    parser.add_argument('data',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('--deadline',required=True)
    parser.add_argument('--per-stage',type=int,default=1)
    args=parser.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    deadline=datetime.fromisoformat(args.deadline).timestamp()
    token=identity(args.pid)
    while token is not None and identity(args.pid)==token:
        if time.time()>=deadline: raise SystemExit('Validation deadline reached before training exited')
        time.sleep(10)
    adapters=[args.run/stage/'best_adapter' for stage in STAGES
              if (args.run/stage/'best_adapter/adapter_manifest.json').exists()]
    if not adapters: raise SystemExit('No complete stage adapters to compare')
    if deadline-time.time()<300: raise SystemExit('Insufficient validation time reserved')
    command=[sys.executable,str(Path(__file__).with_name('evaluate.py')),str(args.data),
             str(adapters[-1]),str(args.output),'--split','validation','--per-stage',str(args.per_stage),
             '--max-seconds','60','--max-new-tokens','1600']
    for adapter in adapters[:-1]: command.extend(['--additional-adapter',str(adapter)])
    status={'started_at':datetime.now(timezone.utc).isoformat(),'adapters':[str(x) for x in adapters],
            'state':'RUNNING','selection_split':'validation'}
    log=(args.output/'eval.log').open('w')
    process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    status['pid']=process.pid
    (args.output/'process.json').write_text(json.dumps(status,indent=2))
    print('VALIDATION_START',json.dumps(status),flush=True)
    try:
        status['exit_code']=process.wait(timeout=min(1800,deadline-time.time()))
        status['state']='COMPLETE' if status['exit_code']==0 else 'FAILED'
    except subprocess.TimeoutExpired:
        os.killpg(process.pid,signal.SIGTERM)
        try: process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL); process.wait()
        status['state']='STOPPED_TIME_LIMIT'
    finally:
        log.close()
        status['finished_at']=datetime.now(timezone.utc).isoformat()
        (args.output/'process.json').write_text(json.dumps(status,indent=2))
    print('VALIDATION_END',json.dumps(status),flush=True)


if __name__=='__main__': main()
