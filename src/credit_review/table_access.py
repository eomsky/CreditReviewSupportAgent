"""Small table discovery cards; source values remain in immutable artifacts."""
import json


def table_card(row):
    if row.get('kind') != 'table':
        return None
    meta = row.get('metadata', {})
    payload = meta.get('structured') or {}
    elements = [e for e in payload.get('elements', []) if e.get('type') == 'table']
    # Legacy sources with no trustworthy structure retain their existing path.
    if not elements:
        return None
    tables = []
    for element in elements:
        hierarchy = element.get('hierarchy') or {}
        tables.append({
            'title': element.get('title'),
            'physical_table_id': element.get('physical_table_id'),
            'logical_table_id': element.get('logical_table_id'),
            'segment': element.get('segment'),
            'columns': [{k: c[k] for k in ('column_id', 'role', 'path') if k in c}
                        for c in hierarchy.get('columns', [])],
            'rows': [{k: r[k] for k in ('row_id', 'path') if k in r}
                     for r in hierarchy.get('rows', [])],
            'units': [{k: u[k] for k in ('text', 'scope') if k in u}
                      for u in element.get('units', [])],
        })
    return {'section_path': payload.get('section_path', []), 'tables': tables,
            'page_opening':meta.get('page_opening'),
            'locator': {'source_id': row['id'], 'document_id': row['document_id'],
                        'page': row['page'], 'parent_id': row.get('parent_id')},
            'values_loaded': False}


def search_text(source):
    card = table_card(source.model_dump(mode='json'))
    if not card:
        return source.text
    # Index semantic labels only. IDs, JSON keys and numeric cell bodies make
    # unrelated tables look similar and consume retrieval/embedding capacity.
    parts = []
    def add(value):
        if isinstance(value, str) and value.strip(): parts.append(value.strip())
        elif isinstance(value, list):
            for item in value: add(item)
        elif isinstance(value, dict):
            for key in ('text','label','name','title','path'): add(value.get(key))
    add(card.get('section_path'))
    # Page titles restore entity/scope labels missing from structural chunks.
    opening = card.get('page_opening') or {}
    add(opening.get('text','')[:220])
    for table in card['tables']:
        add(table.get('title'))
        for column in table['columns']: add(column.get('path'))
        for row in table['rows']: add(row.get('path'))
        for unit in table['units']: add(unit.get('text'))
    return '\n'.join(dict.fromkeys(parts)) or source.text


def prompt_source(row, loaded=False):
    source = {k: v for k, v in row.items() if k != 'metadata'}
    source['read_complete'] = loaded
    card = table_card(row)
    if card:
        from .evidence_scope import explicit_scope
        source['financial_scope']=explicit_scope(row)
        source['table_index'] = card
        source['values_loaded'] = loaded
        if not loaded:
            source['text'] = ''
            source['read_required'] = 'Discovery only. Use read(source_id) before citing values or building a dataset.'
        else:
            # Complete row segment, including notes/units. Do not duplicate it as
            # both embedding text and a dense per-cell hierarchy.
            elements = row['metadata']['structured']['elements']
            source['text'] = '\n'.join(e.get('content', {}).get('value', '')
                for e in elements if e.get('type') == 'table') or row['text']
            source['table_notes'] = [n for e in elements for n in e.get('notes', [])]
            source['table_index']['values_loaded'] = True
    elif row.get('metadata', {}).get('structured'):
        source['section_path'] = row['metadata']['structured'].get('section_path', [])
    return source
