"""Derive correction bookkeeping from actual edits, preserving model claims."""
import copy


def normalize(checks, changed_ids):
    normalized = copy.deepcopy(checks)
    audit = []
    for check in normalized:
        if check.get('status') != 'corrected':
            continue
        claimed = check.get('affected_paragraph_ids', [])
        actual = [key for key in claimed if key in changed_ids]
        if actual == claimed:
            continue
        audit.append({'category': check.get('category'), 'model_claim': copy.deepcopy(check),
                      'actual_changed_paragraph_ids': actual})
        check['affected_paragraph_ids'] = actual
        if not actual:
            check['status'] = 'unresolved'
            check['reason'] = '실제 본문 변경이 없어 모델의 수정 완료 판정을 인정하지 않음.'
    return normalized, audit
