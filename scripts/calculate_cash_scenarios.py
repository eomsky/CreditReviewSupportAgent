"""Source-bound annual cash scenarios; never infer intra-year liquidity."""
import argparse
import json
from decimal import Decimal
from pathlib import Path


def calculate(text, column):
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.split('|')]
        if len(cells) > column + 1:
            if cells[0] in rows:
                raise ValueError('Duplicate source row: ' + cells[0])
            rows[cells[0]] = cells[1:]

    def amount(label):
        return Decimal(rows[label][column].replace(',', ''))

    opening = amount('기초현금등가물(단기금융상품포함)')
    before = amount('외부자금조달전현금흐름')
    after = amount('외부자금조달후현금흐름')
    closing = amount('기말현금등가물(단기금융상품포함)')
    if opening + after != closing:
        raise ValueError('Source cash bridge does not reconcile')
    financing = after - before
    if financing < 0:
        raise ValueError('Reduced-inflow scenario requires net financing inflow')
    return {
        'opening_including_short_term_instruments': str(opening),
        'cashflow_before_financing': str(before),
        'planned_net_financing': str(financing),
        'planned_closing': str(closing),
        'scenarios': [
            {'financing_fraction': str(f), 'closing': str(opening + before + financing * f)}
            for f in (Decimal('0'), Decimal('0.5'), Decimal('1'))
        ],
        'assumptions': ['Other projected cash flows and opening balance unchanged',
                        'Annual endpoint only; no monthly liquidity or minimum operating cash conclusion',
                        'Opening includes short-term instruments; availability not verified',
                        'Scenario is analyst calculation, not company forecast or funding commitment'],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input'); ap.add_argument('source_id'); ap.add_argument('output')
    ap.add_argument('--column', type=int, default=0)
    a = ap.parse_args()
    body = json.loads(Path(a.input).read_text(encoding='utf-8-sig'))
    report = body.get('report', body)
    source = next(s for s in report['sources'] if s['id'] == a.source_id)
    result = {'source_id': a.source_id, 'source_column_index': a.column,
              'calculation': calculate(source['text'], a.column)}
    Path(a.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result['calculation']['scenarios']))


if __name__ == '__main__':
    main()
