"""Check extracted actual table values before Python can use them.

This validates literal transcription, not row meaning or report conclusions.
Unit conversion and other derived values belong in the calculation stage.
"""
from decimal import Decimal, InvalidOperation
import re


def numeric_literals(text):
    values = set()
    for token in re.findall(r'(?<![\d.])\(?[+−-]?\d[\d,]*(?:\.\d+)?\)?', text):
        negative = token.startswith('(') and token.endswith(')')
        try:
            number = Decimal(token.strip('()').replace(',', '').replace('−', '-'))
            values.add(-number if negative else number)
        except InvalidOperation:
            pass
    return values


def currency_unit(text):
    compact = re.sub(r'\s+', '', str(text)).upper()
    for names, unit in [
        (('KRW_MILLION', '백만원'), 'KRW_MILLION'),
        (('KRW_THOUSAND', '천원'), 'KRW_THOUSAND'),
        (('KRW_BILLION', '십억원'), 'KRW_BILLION'),
        (('KRW_100M', '억원'), 'KRW_100M'),
    ]:
        if any(name in compact for name in names):
            return unit
    if compact in {'KRW', '원'} or re.search(r'단위[:：]원(?:[),）]|$)', compact):
        return 'KRW'
    return None


def validate_table_values(data, sources):
    if data.value_type != 'ACTUAL':
        return
    tables = {}
    for sid, source in sources.items():
        elements = source.get('metadata', {}).get('structured', {}).get('elements', [])
        elements = [e for e in elements if e.get('type') == 'table']
        if not elements:
            continue
        body = '\n'.join(e.get('content', {}).get('value', '') for e in elements)
        if not body.strip():
            continue
        units = {currency_unit(u.get('text', '')) for e in elements for u in e.get('units', [])
                 if u.get('scope') == 'table'} - {None}
        tables[sid] = (numeric_literals(body), units)
    for row, provenance in zip(data.rows, data.cell_sources):
        for column in data.columns:
            value = row[column.name]
            if column.dtype not in {'number', 'integer'} or value is None:
                continue
            refs = provenance.get(column.name, [])
            # Legacy/unstructured evidence continues through existing validation.
            if not refs or any(sid not in tables for sid in refs):
                continue
            wanted = Decimal(str(value))
            unit = currency_unit(column.unit)
            matches = [(sid, tables[sid][1]) for sid in refs if wanted in tables[sid][0]]
            if not matches:
                raise ValueError(f'Raw table value not found for {column.name}={value}; '
                                 'copy the original cell without rounding or unit conversion')
            if unit and all(units and unit not in units for _, units in matches):
                raise ValueError(f'Raw table unit conflicts for {column.name}: {column.unit}; '
                                 'retain source units and convert in Python')
