"""Wait for an already-running C1 process, then run C2 and C3 sequentially."""
import ctypes
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/frozen_candidates/controlled-comparison'


def main():
    OUT.mkdir(exist_ok=True)
    helpers={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'scripts').glob('frozen_*.py')}
    (OUT/'harness-hashes.json').write_text(json.dumps(helpers,indent=2))
    state={'started_at':datetime.now().astimezone().isoformat(),'stage':'waiting_C1','runs':[]}
    def save(): (OUT/'queue-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.restype=ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint32]
    kernel.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=kernel.OpenProcess(0x00100000,False,int(sys.argv[1]))
    if handle:
        try:
            while True:
                outcome=kernel.WaitForSingleObject(handle,1000)
                if outcome==0:break
                if outcome!=258:raise OSError('Process wait failed')
        finally:kernel.CloseHandle(handle)
    for candidate in ['C2','C3']:
        for p,h in helpers.items():
            if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h:raise RuntimeError('Harness changed before comparison: '+p)
        state['stage']=candidate;save()
        with (OUT/(candidate+'.log')).open('w',encoding='utf-8') as log:
            result=subprocess.run([str(ROOT/'outputs/frozen_candidates/parser-env/Scripts/python.exe'),'-X','utf8',str(ROOT/'scripts/frozen_full_test.py'),candidate],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        record={'id':candidate,'process_returncode':result.returncode}
        path=ROOT/'outputs/frozen_candidates'/candidate/'results.json'
        if path.exists():
            data=json.loads(path.read_text(encoding='utf-8'))
            record.update(status=data['status'],elapsed_seconds=data.get('elapsed_seconds'),error=data.get('error'))
        else:record.update(status='process_failed_without_result')
        state['runs'].append(record);save()
    state['stage']='runs_terminal_quality_review_required';save()


if __name__=='__main__':main()
