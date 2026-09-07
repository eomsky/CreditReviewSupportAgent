import json
from pathlib import Path
from datetime import date
from collections import Counter
import argparse
from credit_review.models import Source
from credit_review.retrieval import Retriever
from credit_review.evidence_queries import QUERIES

p = argparse.ArgumentParser()
p.add_argument('run', type=Path)
a = p.parse_args()
raw = json.loads(next(a.run.glob('artifacts/sources_*.json')).read_text())['payload']['sources']
sources = [Source.model_validate(r) for r in raw]
r = Retriever(sources, date(2026,4,7))
print('SOURCES', len(sources), dict(Counter(s.kind for s in sources)))
print('SEARCHABLE', len(r.rows), 'CHARS', sum(len(s.text) for s in r.rows))
for fid in ['F03','F13','F14','F15','F16','F21']:
    print('\nFACTOR', fid, QUERIES[fid])
    for hit in r.search(QUERIES[fid], limit=4):
        s = hit['source']
        print(s['id'], 'page',s['page'], s['kind'], 'chars',len(s['text']))
        print(s['text'][:350].replace('\n',' '))
