"""Select the existing removal-prefix boundary with fewer token counter calls."""


def removal_order(evidence, protected):
    counts = {}
    for source in evidence:
        key = source['document_id']
        counts[key] = counts.get(key, 0) + 1
    removed = []
    for i in range(len(evidence)-1, -1, -1):
        source = evidence[i]
        if source['id'] in protected:
            continue
        if source.get('metadata', {}).get('required', False) and counts[source['document_id']] <= 1:
            continue
        if len(evidence)-len(removed) <= 1:
            break
        removed.append(i)
        counts[source['document_id']] -= 1
    return removed


def fit_evidence(evidence, protected, evaluate, reserve):
    """evaluate returns (messages, aliases, token_count, maximum).

    Preserve removal order and the exact untouched evidence objects. This is a
    candidate optimization; real tokenizer boundary equivalence is a QA gate.
    """
    order = removal_order(evidence, protected)
    cache = {}
    def probe(n):
        if n not in cache:
            drop = set(order[:n])
            rows = [s for i,s in enumerate(evidence) if i not in drop]
            cache[n] = (rows, evaluate(rows))
        return cache[n]
    def fits(n):
        _, (_, _, count, maximum) = probe(n)
        return count + reserve <= maximum
    if fits(0):
        return probe(0)
    if not fits(len(order)):
        return probe(len(order))
    lo, hi = 0, len(order)
    while hi-lo > 1:
        mid = (lo+hi)//2
        if fits(mid): hi=mid
        else: lo=mid
    return probe(hi)
