"""Experimental retrieval: rank pages jointly, preserve full frozen page evidence."""
import re
from collections import defaultdict

from frozen_original_vector_sources import OriginalVectorStore


def compact_layout(text):
    # Preserve every non-whitespace character and column separator; remove PDF padding.
    return re.sub(r'\n[ \t]*\n+', '\n', re.sub(r' {2,}', '\t', text))


def page_bundles(sources):
    groups = defaultdict(list)
    for source in sources:
        if len(re.findall(r'\.{5,}', source['text'])) >= 3:
            continue
        is_pdf = source.get('format') == 'pdf' or ('page' in source and 'bbox' in source)
        key = ('page', source['page']) if is_pdf else ('source', source['id'])
        groups[key].append({**source, 'text': compact_layout(source['text'])} if is_pdf else source)
    return groups


class PageVectorStore(OriginalVectorStore):
    def get(self, key):
        doc=super().get(key)
        if doc.get('format')=='pdf':
            return {**doc,'sources':[{**s,'text':compact_layout(s['text'])} for s in doc['sources']]}
        return doc

    def select(self, terms, manifest, budget=16000, limit=24):
        from review_documents import DocumentError, PRIORITIES
        candidates = []
        for meta in manifest:
            sources = self.get(meta['id'])['sources']
            groups = page_bundles(sources)
            source_group = {s['id']: key for key, rows in groups.items() for s in rows}
            scores = defaultdict(float)
            # RRF combines ranks, never incomparable cosine/keyword raw scores.
            lexical = self.keyword.select(terms, [meta], budget=max(budget, 64000), limit=64)
            dense = self.vector.search(' '.join(terms), meta['id'], 64) if meta['id'] in self.documents else []
            for ranking in ([s['id'] for s in lexical], [sid for sid, _ in dense]):
                ranked_groups = list(dict.fromkeys(source_group[sid] for sid in ranking if sid in source_group))
                for rank, key in enumerate(ranked_groups):
                    scores[key] += 1 / (60 + rank + 1)
            for key, score in scores.items():
                rows = sorted(groups[key], key=lambda s: (s.get('bbox', [0, 0])[1], s['id']))
                # A title match is more specific than repeated mentions in accounting notes.
                opening = re.sub(r'\s+', '', rows[0]['text'].splitlines()[0])
                specific = [re.sub(r'\s+', '', term) for term in terms if len(re.sub(r'\s+', '', term)) >= 5]
                if len(opening) <= 60 and any(term in opening for term in specific):
                    score *= 4
                elif len(opening) <= 100 and specific:
                    # Character overlap tolerates Korean particles without a company/metric alias list.
                    header_pairs = {opening[i:i+2] for i in range(len(opening)-1)}
                    overlaps = [len(header_pairs & {term[i:i+2] for i in range(len(term)-1)}) / (len(term)-1)
                                for term in specific]
                    score *= 1 + 2 * max(overlaps)
                if key[0] == 'page':
                    following = groups.get(('page', key[1]+1), [])
                    if following:
                        first = min(following, key=lambda s:s.get('bbox',[0,0])[1])['text'][:250]
                        new_heading = re.search(r'계\s*산\s*서|변\s*동\s*표|재\s*무\s*상\s*태\s*표|주\s*석|제\s*\d+.*기', first)
                        continued_numbers = len(re.findall(r'\d{1,3}(?:,\d{3})+', first)) >= 3
                        if not new_heading and continued_numbers:
                            rows += sorted(following, key=lambda s:(s.get('bbox',[0,0])[1],s['id']))
                candidates.append((score * PRIORITIES[meta['priority']], meta, rows))
        candidates.sort(key=lambda entry: (-entry[0], entry[1]['id'], entry[2][0]['id']))
        chosen, seen, used = [], set(), 0

        def add(entry, mandatory=False):
            nonlocal used
            score, meta, rows = entry
            fresh = [s for s in rows if s['id'] not in seen]
            size = sum(len(s['text']) for s in fresh)
            if not fresh:
                return True
            if (not mandatory and len(chosen)+len(fresh)>limit) or used + size > budget:
                return False
            for s in fresh:
                chosen.append({**s, 'document_name': meta['name'], 'metadata': meta,
                               'selection_relevance': score, 'retrieval_mode': 'page_rrf'})
                seen.add(s['id'])
            used += size
            return True

        for meta in manifest:
            if meta['required'] and not any(add(c, mandatory=True) for c in candidates if c[1]['id'] == meta['id']):
                raise DocumentError('필수 자료의 완전한 근거를 담기에 분석 용량이 부족합니다.')
        for candidate in candidates:
            add(candidate)
        return chosen
