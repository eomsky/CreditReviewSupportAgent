"""Remove orchestration duplication without summarizing or cutting source text."""
from copy import deepcopy


def compact_group_context(context):
    result = deepcopy(context)
    for factor in result.get('factors', {}).values():
        # These are orchestration/UI bookkeeping, not evidence or analysis inputs.
        for key in ('review_date', 'mode', 'source_window'):
            factor.pop(key, None)
        state = factor.get('state', {})
        for key in ('factor_id', 'status', 'steps', 'report_text', 'last_signature',
                    'repeated_actions', 'consecutive_errors', 'recent_source_ids'):
            state.pop(key, None)
        # Current sources have one common catalog; prior unseen IDs remain readable.
        state['evidence_ids'] = [sid for sid in state.get('evidence_ids', [])
                                 if sid not in result.get('sources', {})]
        for key in list(state):
            if state[key] is None or state[key] == []:
                del state[key]
    # An ID is already the dictionary key; keep document/page/date/scope/structure.
    for sid, source in result.get('sources', {}).items():
        if source.get('id') == sid:
            source.pop('id')
    result['shared_source_access'] = 'All source catalog keys are available evidence IDs for every factor; prior findings are not verified facts.'
    return result
