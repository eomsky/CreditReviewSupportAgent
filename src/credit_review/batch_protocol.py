"""Wire-only row pairing; persistent datasets keep their validated schema."""
import json
import re
from decimal import Decimal
from copy import deepcopy


def pair_dataset_schema(schema):
    # Runtime numeric validation already requires units. Enforce the same rule
    # during generation rather than spending another LLM call repairing nulls.
    column = schema['$defs']['Column']
    numeric, descriptive = deepcopy(column), deepcopy(column)
    numeric['properties']['dtype'] = {'type':'string','enum':['number','integer']}
    numeric['properties']['unit'] = {'type':'string','minLength':1}
    numeric['required'] = list(dict.fromkeys(numeric['required'] + ['unit']))
    descriptive['properties']['dtype'] = {'type':'string','enum':['string','boolean']}
    schema['$defs']['Column'] = {'anyOf':[numeric,descriptive]}
    dataset = schema['$defs']['Dataset']
    props = dataset['properties']
    values, sources = props.pop('rows'), props.pop('cell_sources')
    props['records'] = {'type':'array', 'minItems':1, 'items':{
        'type':'object', 'additionalProperties':False,
        'properties':{'values':values['items'], 'sources':sources['items']},
        'required':['values','sources']}}
    dataset['required'] = [k for k in dataset['required'] if k not in ('rows','cell_sources')] + ['records']


def unpack_dataset_rows(raw):
    reply = json.loads(raw)
    for item in reply.get('actions', []):
        action = item.get('action', {})
        if action.get('action') == 'dataset' and 'records' in action.get('dataset', {}):
            data = action['dataset']
            if 'rows' in data or 'cell_sources' in data:
                raise ValueError('Ambiguous dataset row representations')
            records = data.pop('records')
            if not isinstance(records, list) or any(set(r) != {'values','sources'} for r in records):
                raise ValueError('Each dataset record needs values and sources')
            data['rows'] = [r['values'] for r in records]
            data['cell_sources'] = [r['sources'] for r in records]
    # No provenance is invented or broadcast. Normal Dataset validation still runs.
    return json.dumps(reply, ensure_ascii=False, separators=(',', ':'))


def cell_dataset_schema(schema, source_ids):
    """Place every raw value beside its provenance; avoid parallel free-form maps."""
    pair_dataset_schema(schema)
    cell = {'type':'object', 'additionalProperties':False,
            'properties':{'column':{'type':'string','minLength':1},
                          'value':{'anyOf':[{'type':'number'},{'type':'string'},
                                            {'type':'boolean'},{'type':'null'}]},
                          'source_ids':{'type':'array','items':{'type':'string','enum':list(source_ids)},
                                        'minItems':1,'maxItems':3}},
            'required':['column','value','source_ids']}
    schema['$defs']['Dataset']['properties']['records'] = {
        'type':'array','minItems':1,'maxItems':3,'items':{
            'type':'object','additionalProperties':False,
            'properties':{'cells':{'type':'array','minItems':1,'maxItems':8,'items':cell}},
            'required':['cells']}}


def unpack_cell_records(reply):
    for item in reply.get('datasets', []):
        data = item['dataset']
        if 'rows' in data or 'cell_sources' in data:
            raise ValueError('Ambiguous dataset row representations')
        records = data.pop('records')
        numeric={c['name'] for c in data['columns'] if c['dtype'] in {'number','integer'}}
        rows, provenance = [], []
        for record in records:
            row, refs = {}, {}
            for cell in record['cells']:
                name = cell['column']
                if name in row:
                    raise ValueError('Duplicate column in extracted record: '+name)
                row[name], refs[name] = cell['value'], cell['source_ids']
                if name in numeric and isinstance(row[name],str):
                    literal=row[name].strip()
                    if re.fullmatch(r'[+-]?\d+(?:\.\d+)?',literal):
                        number=Decimal(literal)
                        row[name]=int(number) if number==number.to_integral_value() else float(number)
            rows.append(row)
            provenance.append(refs)
        data['rows'], data['cell_sources'] = rows, provenance
    return reply
