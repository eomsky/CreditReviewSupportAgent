"""Experimental SPT JSON -> lossless cell frame. Does not modify report generation."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import pandas as pd


def cell_frame(chunks, document_hash, table_metadata=None):
    """Retain physical identity, header paths, units and raw text; infer no values."""
    records = {}
    table_metadata = table_metadata or {}
    for chunk in chunks:
        payload = json.loads(chunk['document'])
        for table in payload.get('elements', []):
            if table.get('type') != 'table':
                continue
            h = table['hierarchy']
            rows = {r['row_id']: r for r in h['rows']}
            columns = {c['column_id']: c for c in h['columns']}
            for cell in h['cells']:
                key = document_hash + ':' + cell['source_cell_id']
                parser = table_metadata.get(table['physical_table_id'], {})
                record = dict(cell_id=key, raw_value=cell['value'],
                    parser_status=parser.get('status', 'UNKNOWN'),
                    content_type=cell['content_type'],
                    row_path=rows[cell['row_id']]['path'],
                    column_path=columns[cell['column_id']]['path'],
                    row_sources=rows[cell['row_id']]['source_cell_ids'],
                    column_sources=columns[cell['column_id']]['source_cell_ids'],
                    physical_table_id=table['physical_table_id'],
                    logical_table_id=table['logical_table_id'],
                    title=table['title'], units=table['units'], notes=table['notes'],
                    unit_refs=cell['unit_refs'], source=payload['source'])
                if key in records and records[key] != record:
                    raise ValueError('Conflicting repeated physical cell: ' + key)
                records[key] = record
    if not records:
        return pd.DataFrame(columns=['cell_id','physical_table_id','parser_status'], dtype=object)
    return pd.DataFrame(list(records.values()), dtype=object)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('chunks', type=Path)
    p.add_argument('pdf', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--master', type=Path)
    a = p.parse_args()
    chunks = json.loads(a.chunks.read_text(encoding='utf-8'))
    if isinstance(chunks, dict): chunks = chunks['chunks']
    digest = hashlib.sha256(a.pdf.read_bytes()).hexdigest()
    start = perf_counter()
    metadata = {}
    if a.master:
        master = json.loads(a.master.read_text(encoding='utf-8'))
        metadata = {t['table_id']:t for t in master['semantic_elements']['tables']}
    frame = cell_frame(chunks, digest, metadata)
    # Pandas to_json rounds nested bbox floats at its default precision.
    encoded = json.dumps(frame.to_dict(orient='records'), ensure_ascii=False, allow_nan=False)
    restored = json.loads(encoded)
    assert restored == frame.to_dict(orient='records'), 'Loss during serialization'
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output/'cells.json').write_text(encoded, encoding='utf-8')
    result = dict(cells=len(frame), tables=frame.physical_table_id.nunique(),
        conversion_seconds=perf_counter()-start, document_sha256=digest,
        roundtrip_exact=True, end_to_end=False,
        parser_status_cells=frame.parser_status.value_counts().to_dict(),
        note='Structural transfer only; no semantic period/unit validation or report integration.')
    (a.output/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
