"""Check stock/flow reconciliation without confusing opening cash with inflows."""
from decimal import Decimal


def reconcile(before, financing, after, opening, closing):
    values = [Decimal(str(v)) for v in (before, financing, after, opening, closing)]
    before, financing, after, opening, closing = values
    if not all(v.is_finite() for v in values):
        raise ValueError('Non-finite cashflow value')
    return {'before_financing_flow': str(before), 'financing_flow': str(financing),
            'after_financing_flow': str(after), 'opening_cash_balance': str(opening),
            'closing_cash_balance': str(closing),
            'flow_reconciles': before + financing == after,
            'balance_reconciles': opening + after == closing,
            'opening_balance_included_in_after_financing_flow': False,
            'equations': ['before_financing_flow + financing_flow = after_financing_flow',
                          'opening_cash_balance + after_financing_flow = closing_cash_balance']}


def from_source(source, column=0):
    labels = ['외부자금조달전현금흐름', '자본증감액', '단기차입금증감액',
              '장기차입금증감액', '회사채및상환우선주 등 증감액',
              '외부자금조달후현금흐름', '기초현금등가물(단기금융상품포함)',
              '기말현금등가물(단기금융상품포함)']
    rows = {}
    for line in source['text'].splitlines():
        cells = [s.strip() for s in line.split('|')]
        if cells[0] in labels:
            if cells[0] in rows or len(cells) <= column + 1:
                raise ValueError('Ambiguous or missing cashflow column')
            rows[cells[0]] = Decimal(cells[column+1].replace(',', ''))
    if set(rows) != set(labels):
        raise ValueError('Incomplete cashflow bridge')
    result = reconcile(rows[labels[0]], sum(rows[k] for k in labels[1:5]),
                       rows[labels[5]], rows[labels[6]], rows[labels[7]])
    result.update(source_id=source['id'], document_id=source['document_id'],
                  numeric_column_index=column, original_rows={k:str(v) for k,v in rows.items()},
                  semantic_approval='pending LLM review of period and row meaning')
    return result
