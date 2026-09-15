"""Locate cash-flow facts with explicit period/unit provenance for LLM approval.

Candidates are not approved facts. Continuation fragments require review of
their document/column linkage before they can be materialized in a report.
"""
import re
from decimal import Decimal


def candidates(sources):
    output = []
    for head in sources:
        text = head['text']
        compact = re.sub(r'\s+', '', text)
        if '현금흐름표' not in compact:
            continue
        periods = re.findall(r'제\s*\d+\s*\([^)]*\)\s*기\s*:\s*(\d{4})년', text)
        unit = re.search(r'단위\s*:\s*(백만원|천원|원)', text)
        if len(periods) != 2 or len(set(periods)) != 2 or not unit:
            continue
        scale = {'원': Decimal('0.000001'), '천원': Decimal('0.001'), '백만원': Decimal(1)}[unit[1]]
        basis = 'consolidated' if '연결현금흐름표' in compact else 'unknown'
        for source in sources:
            if source['document_id'] != head['document_id']:
                continue
            for line in source['text'].splitlines():
                clean = re.sub(r'\s+', '', line)
                account = next((name for name, pattern in (
                    ('operating_cashflow', '영업활동으로인한현금흐름'),
                    ('investing_cashflow', '투자활동으로인한현금흐름'),
                    ('financing_cashflow', '재무활동으로인한현금흐름'),
                    ('closing_cash', '기말의?현금및현금성자산'),
                ) if re.search(pattern, clean)), None)
                if account is None:
                    continue
                # Tabular columns are separated by at least two spaces. Do not
                # confuse Roman row numbers or note references with values.
                columns = re.split(r'\s{2,}', line.strip())
                values = columns[-2:]
                if len(columns) < 3 or any(not re.fullmatch(r'\(?-?\d[\d,]*(?:\.\d+)?\)?', v) for v in values):
                    continue
                for period, raw in zip(periods, values):
                    value = Decimal(raw.replace(',', '').replace('(', '-').replace(')', ''))
                    output.append({'account': account, 'period': period,
                                   'raw_value': raw, 'raw_unit': unit[1],
                                   'value_million_won': str(value * scale),
                                   'basis': basis, 'document_id': source['document_id'],
                                   'source_id': source['id'], 'header_source_id': head['id'],
                                   'source_line': line.strip(),
                                   'continuation_requires_review': source['id'] != head['id'],
                                   'approval_status': 'pending'})
    return output
