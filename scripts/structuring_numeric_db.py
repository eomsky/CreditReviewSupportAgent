"""Structuring experiment: immutable source cells and separately reviewed facts."""
import argparse, hashlib, json, re, sqlite3, time
from pathlib import Path

SCHEMA = """
CREATE TABLE documents(id TEXT PRIMARY KEY, name TEXT, sha256 TEXT);
CREATE TABLE sources(id TEXT PRIMARY KEY, document_id TEXT, sheet TEXT, page INTEGER, raw_text TEXT);
CREATE TABLE cells(id INTEGER PRIMARY KEY, source_id TEXT, row_number INTEGER, column_name TEXT, raw_value TEXT, row_label TEXT, numeric_lexeme TEXT);
CREATE INDEX cells_label ON cells(row_label);
CREATE TABLE facts(id INTEGER PRIMARY KEY, cell_id INTEGER, entity TEXT, account TEXT, period TEXT, basis TEXT, unit TEXT, value_decimal TEXT, review_status TEXT NOT NULL DEFAULT 'pending', review_evidence TEXT);
CREATE TABLE normalization_reviews(id INTEGER PRIMARY KEY, fact_id INTEGER, model TEXT, request_sha256 TEXT, decision TEXT, reason TEXT);
CREATE VIEW approved_facts AS SELECT facts.*,cells.source_id,cells.row_number,cells.column_name FROM facts JOIN cells ON facts.cell_id=cells.id WHERE review_status='approved';
"""

def build(document_path, output):
    started=time.monotonic();document_path=Path(document_path);output=Path(output)
    if output.exists():raise FileExistsError(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    document=json.loads(document_path.read_text(encoding='utf-8-sig'))
    connection=sqlite3.connect(output);connection.executescript(SCHEMA)
    connection.execute('INSERT INTO documents VALUES (?,?,?)',(document['id'],document.get('name'),hashlib.sha256(document_path.read_bytes()).hexdigest()))
    for source in document['sources']:
        connection.execute('INSERT INTO sources VALUES (?,?,?,?,?)',(source['id'],document['id'],source.get('sheet'),source.get('page'),source['text']))
        for line in source['text'].splitlines():
            parts=[re.fullmatch(r'([A-Z]+)([0-9]+)=(.*)',part.strip()) for part in line.split('|')]
            matches=[m for m in parts if m]
            if not matches:continue
            label=matches[0].group(3)
            for match in matches:
                col,row,raw=match.groups()
                numeric=raw.replace(',','').strip()
                if not re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?',numeric):numeric=None
                # Numeric recognition is lexical only: dates, ratios and sentinel
                # values are not automatically promoted to accounting facts.
                connection.execute('INSERT INTO cells(source_id,row_number,column_name,raw_value,row_label,numeric_lexeme) VALUES (?,?,?,?,?,?)',(source['id'],int(row),col,raw,label,numeric))
    connection.commit()
    counts={name:connection.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ['sources','cells','facts','approved_facts']}
    connection.close()
    return {'elapsed_seconds':round(time.monotonic()-started,4),'counts':counts,'normalization_review_completed':False,'end_to_end':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('document');parser.add_argument('output');args=parser.parse_args()
    print(json.dumps(build(args.document,args.output),ensure_ascii=False))
