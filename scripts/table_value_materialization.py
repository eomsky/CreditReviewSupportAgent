"""Exact arithmetic for selected source cells; not a semantic approval mechanism."""
import re
from decimal import Decimal, ROUND_HALF_UP, localcontext

SCALES={'원':Decimal(1),'천원':Decimal(1000),'백만원':Decimal(1000000),'억원':Decimal(100000000)}


def parse_amount(raw):
    if not isinstance(raw,str):raise ValueError('Source value must retain original text')
    value=raw.strip()
    if value in ('','—','–','-','N/A','n/a'):return None
    negative=value.startswith('(') and value.endswith(')')
    if negative:value=value[1:-1].strip()
    pattern=r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?'
    if not re.fullmatch(pattern,value) or (negative and value[0] in '+-'):
        raise ValueError('Ambiguous numeric notation requires review')
    amount=Decimal(value.replace(',',''))
    return -amount if negative else amount


def materialize_money(cell_id, cells, source_unit, target_unit, places=0):
    if cell_id not in cells:raise ValueError('Unknown source cell')
    if source_unit not in SCALES or target_unit not in SCALES:raise ValueError('Unsupported monetary unit')
    if type(places) is not int or not 0<=places<=8:raise ValueError('Invalid output precision')
    cell=cells[cell_id]
    declared=set()
    for unit in cell.get('units',[]):
        for match in re.finditer(r'단위\s*[:：]\s*([^）)\]\n]+)',unit.get('text','')):
            # Mixed monetary/% tables must be resolved at cell level, not guessed.
            label=match[1].strip()
            if label in SCALES:declared.add(label)
            else:raise ValueError('Mixed or unknown unit requires semantic resolution')
    if declared!={source_unit}:raise ValueError('Requested unit does not match explicit source metadata')
    amount=parse_amount(cell['raw_value'])
    result={'cell_id':cell_id,'raw_value':cell['raw_value'],'source_unit':source_unit,
            'target_unit':target_unit,'row_path':cell['row_path'],'column_path':cell['column_path'],
            'semantic_review_required':True,'parser_status':cell.get('parser_status','UNKNOWN')}
    if amount is None:return {**result,'value':None,'exact_value':None}
    with localcontext() as context:
        context.prec=max(40,len(amount.as_tuple().digits)+24)
        exact=amount*SCALES[source_unit]/SCALES[target_unit]
        rounded=exact.quantize(Decimal(1).scaleb(-places),rounding=ROUND_HALF_UP)
    # Decimal strings avoid JSON floating-point changes. Renderer chooses formatting.
    return {**result,'value':str(rounded),'exact_value':str(exact),'rounding':'ROUND_HALF_UP'}
