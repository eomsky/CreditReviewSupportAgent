"""Private evaluation archive. Never put this output in Git."""
import json
import zipfile
from pathlib import Path
from datetime import datetime,timezone
from credit_review.store import atomic_json

root=Path('workspace/benchmarks')
since=datetime(2026,9,7,16,49,39,tzinfo=timezone.utc).timestamp()
target=root/'overnight_v1_evidence.zip'
selected=[]
for run in (root/'cases/full/runs').glob('run_*'):
    state=run/'state.json'
    if state.exists() and state.stat().st_mtime>=since:
        selected.extend(p for p in run.rglob('*') if p.is_file() and p.name!='.run.lock')
selected.extend(p for p in root.glob('watch_*') if p.stat().st_mtime>=since)
selected.extend(p for p in (root/'ingestion').glob('*/summary.json'))
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for path in sorted(set(selected)): z.write(path,str(path.relative_to(root)))
import hashlib
print(json.dumps({'archive':str(target),'bytes':target.stat().st_size,'files':len(selected),
    'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}),flush=True)
