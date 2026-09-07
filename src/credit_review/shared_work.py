"""Run-local retrieval of prior requests and results; never a cache of truth."""
import hashlib
import json
import re

from .models import Action


def terms(text):
    words = re.findall(r'[\w]+', text.lower())
    return set(words) | {word[i:i+2] for word in words for i in range(len(word)-1)}


def signature(action):
    value = action.model_dump(mode='json', exclude_none=True, exclude={'reason', 'inquiry'})
    if action.action == 'search':
        value['query'] = ' '.join(action.query.split())
    if action.action == 'read':
        value['source_ids'] = sorted(set(action.source_ids))
    if action.action == 'calculate':
        # Preserve code, assumptions and dataset identities, including their scope.
        value['calculation'].pop('purpose', None)
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class SharedWork:
    def __init__(self, h):
        self.h = h
        self.records = []
        self.exact = {}
        for path in sorted((h.store.path/'artifacts').glob('shared_work_*.json'), key=lambda p:p.stat().st_mtime_ns):
            row = json.loads(path.read_text(encoding='utf-8'))['payload']
            if row['source_revision'] == h.state.source_revision:
                self._index(row)
        # Discover historical replies from pre-coordinator runs, without blessing them.
        covered = {r['request_id'] for r in self.records}
        outputs = [p for pattern in ('llm_output_*.json', 'group_output_*.json')
                   for p in (h.store.path/'artifacts').glob(pattern)]
        for path in sorted(outputs, key=lambda p:p.stat().st_mtime_ns)[-40:]:
            artifact = json.loads(path.read_text(encoding='utf-8'))
            if artifact['id'] in covered:
                continue
            self.records.append({'request_id': artifact['inputs'][0] if artifact['inputs'] else None,
                'result_id': artifact['id'], 'summary': artifact['payload'].get('raw','')[:2200],
                'verification': 'unverified_historical_llm_reply; inspect original evidence'})
        self.refresh()

    def _index(self, row):
        self.records.append(row)
        if row.get('signature') and not row.get('error'):
            self.exact[row['signature']] = row

    def refresh(self):
        # Older runs may contain useful assets but no shared-work records.
        self.assets = {}
        for fid, f in self.h.state.factors.items():
            for kind, ids in (('dataset', f.dataset_ids), ('calculation', f.calculation_ids)):
                for aid in ids:
                    payload = self.h.store.get(aid)['payload']
                    self.assets[aid] = {'factor_id': fid, 'kind': kind, 'artifact_id': aid,
                        'summary': json.dumps(payload, ensure_ascii=False)[:1800],
                        'verification': 'schema_and_provenance_checked' if kind == 'dataset'
                            else payload.get('status', 'UNKNOWN')}
            if f.judgement:
                self.assets[fid] = {'factor_id': fid, 'kind': 'judgement',
                    'summary': f.judgement.summary, 'evidence_ids': f.judgement.evidence_ids,
                    'verification': 'reference_integrity_only; semantic_review_pending'}

    def search(self, query, limit=5):
        query_terms = terms(query)
        candidates = list(self.assets.values()) + self.records
        ranked = []
        for i, row in enumerate(candidates):
            score = len(query_terms & terms(row.get('summary', '')))
            if score:
                ranked.append((score, i, row))
        return [dict(row) for _, _, row in sorted(ranked, key=lambda x: (x[0], x[1]), reverse=True)[:limit]]

    def record(self, fid, action, parent, result=None, error=None):
        f = self.h.state.factors[fid]
        payload = self.h.store.get(result)['payload'] if result else {}
        row = {'source_revision': self.h.state.source_revision, 'factor_id': fid,
            'signature': signature(action), 'action': action.action,
            'request_id': parent, 'result_id': result, 'error': error,
            'summary': json.dumps({'request': action.model_dump(mode='json', exclude_none=True),
                'result': payload}, ensure_ascii=False)[:2200],
            'evidence_ids': list(f.recent_source_ids) if action.action in ('read', 'search') else [],
            'dataset_ids': [result] if action.action == 'dataset' and result else [],
            'calculation_ids': [result] if action.action == 'calculate' and result else [],
            'verification': 'execution_failed' if error else
                ('source_candidates_only' if action.action in ('search', 'read') else
                 'reference_integrity_only; semantic_review_pending')}
        self.h.store.put('shared_work', row, [parent] + ([result] if result else []))
        self._index(row)

    def reuse_exact(self, fid, action, parent):
        if action.action not in ('search', 'read', 'dataset', 'calculate'):
            return None
        row = self.exact.get(signature(action))
        if not row:
            return None
        f = self.h.state.factors[fid]
        if row['evidence_ids']:
            self.h.apply(fid, Action(action='read', reason='Reuse prior source lookup',
                source_ids=row['evidence_ids']), parent)
        for aid in row['dataset_ids']:
            self.h.apply(fid, Action(action='reuse', reason='Reuse identical validated dataset',
                reuse_dataset_ids=[aid]), parent)
        for aid in row['calculation_ids']:
            payload = self.h.store.get(aid)['payload']
            if payload.get('status') != 'EXECUTED':
                return None
            self.h.apply(fid, Action(action='reuse', reason='Reuse executed calculation inputs',
                reuse_dataset_ids=payload['plan']['dataset_ids']), parent)
            if aid not in f.calculation_ids:
                f.calculation_ids.append(aid)
        self.h.store.event(action='shared_exact_reuse', factor_id=fid, result_id=row['result_id'])
        return row['result_id']
