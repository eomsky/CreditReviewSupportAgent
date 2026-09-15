"""Replace serial token-budget probes, retaining original message construction."""
import ast


def patch(source):
    start = source.index('    while True:\n        aliases =', source.index('def complete('))
    end = source.index("    paragraph['properties']['source_ids']", start)
    original = source[start:end]
    builder = original[original.index('        aliases ='):original.index('        if count+output_budget')]
    builder = builder.replace('enumerate(evidence)', 'enumerate(rows)')
    replacement = '''    from frozen_budget_search import fit_evidence
    def evaluate_evidence(rows):
'''+builder+'''        return messages, aliases, count, context_limit
    initial = evaluate_evidence(evidence)
    if initial[2]+output_budget+256 > initial[3] and drafts and not report:
        drafts = {}
    evidence, fitted = fit_evidence(evidence, planned_ids, evaluate_evidence, output_budget+256)
    messages, aliases, count, context_limit = fitted
'''
    result = source[:start]+replacement+source[end:]
    ast.parse(result)
    return result
