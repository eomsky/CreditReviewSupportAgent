"""Wire-only row pairing; persistent datasets keep their validated schema."""
import json


def pair_dataset_schema(schema):
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
