"""Compact local diagnostics; no connection credentials or raw PDF dump."""
import json
from collections import Counter
from pathlib import Path
import argparse

p = argparse.ArgumentParser()
p.add_argument('run', nargs='?', type=Path)
a = p.parse_args()
root = a.run or max(Path('workspace/benchmarks/cases/full/runs').glob('run_*'), key=lambda p:p.stat().st_mtime_ns)
print(root)
state = json.loads((root/'state.json').read_text())
summary = root/'benchmark_summary.json'
if summary.exists():
    s = json.loads(summary.read_text())
    print(json.dumps({k:s.get(k) for k in ['elapsed_seconds','stage','error','judgements','fulfilled','report_completed']}, ensure_ascii=False))
actions = []
for path in sorted(root.glob('artifacts/group_output_*.json'), key=lambda p:p.stat().st_mtime_ns):
    row = json.loads(path.read_text())
    try:
        items = json.loads(row['payload']['raw'])['actions']
    except (ValueError, KeyError):
        continue
    for item in items:
        act = item['action']
        actions.append(act['action'])
        print(item['factor_id'], act['action'], (act.get('query') or ','.join(act.get('source_ids', [])) or act.get('reason',''))[:180])
print('ACTIONS', dict(Counter(actions)))
print('DATASETS', len(list(root.glob('artifacts/dataset_*.json'))), 'CALCULATIONS', len(list(root.glob('artifacts/calculation_*.json'))))
print('FACTOR_ERRORS', json.dumps({fid: f['error'] for fid,f in state['factors'].items() if f.get('error')}, ensure_ascii=False))
for pattern in ['foundation_limitations_*.json','calculation_*.json']:
    for path in root.glob('artifacts/'+pattern):
        row=json.loads(path.read_text())['payload']
        print(path.stem, json.dumps({k:row[k] for k in ['status','result','limitations','errors'] if k in row},ensure_ascii=False)[:1800])
if (root/'performance.json').exists():
    perf=json.loads((root/'performance.json').read_text())
    for item in perf.get('operations',[]):
        if item['kind'].startswith('llm_'):
            print('TIMING',item['kind'],round(item['seconds'],2))
