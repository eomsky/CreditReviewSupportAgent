"""Lossless source grids, LLM-reviewed metadata and parameterized SQL retrieval.

The model assigns meaning/coordinates; it never supplies stored numeric values.
Unmapped or ambiguous sources remain available to the ordinary evidence path.
"""
import hashlib
import json
import re
import sqlite3
from decimal import Decimal, InvalidOperation
from pathlib import Path
from contextlib import contextmanager

VERSION = 'C20.47.3'
# Transport/budget patches must not invalidate accepted semantic reviews.
NORMALIZATION_VERSION = 'C20.47.2'
READ_RULES = 'structured_sql은 원문 셀과 검수 메타데이터를 SQL로 조회한 자료다. value는 원문 단위의 정확한 숫자 문자열이다. 표시 단위가 다르면 명시적으로 환산하고 원문 단위와 혼합하지 않는다. 기간·기업·연결/별도·표 제목이 다른 값은 합치지 않는다. basis가 비어 있으면 기준 미확정이다. 서로 다른 review_id의 같은 셀 해석이 다르면 충돌을 검토한다. SQL에 없는 항목은 제공된 원문에서 계속 확인한다. 원문 인용은 source_ids를 사용한다.'
RULES = '''structured_grids는 원문에서 보존한 셀 좌표다. structured_tables에는 아직 검수하지 않은 표의 메타데이터와 행/열 대응만 반환한다. 숫자 자체를 다시 생성하지 않는다.
표 제목·목차·머리글·단위·기간·연결/별도·기업 범위를 함께 확인한다. 다른 위치의 유사 표를 합치지 않는다. source_id는 원문 별칭이다. title_quote, basis_quote, unit_quote, period_quote는 같은 원문의 연속된 문구를 그대로 복사한다. basis, unit, period는 각각 해당 quote 안에서 직접 확인되는 표현만 사용하며 추정하지 않는다. 모르면 빈 문자열로 둔다.
columns의 column은 실제 열 좌표이며 period와 unit은 그 열의 원문 기간·단위다. rows의 row는 실제 행 좌표, metric은 그 행에 실제로 있는 항목명, unit은 그 행에 명시된 단위(없으면 빈 문자열)다. 병합 머리글의 의미가 불분명하면 해당 행/열을 대응하지 않는다. 서로 다른 기간·기준·표를 하나로 합치지 않는다.
표의 모든 확인 가능한 수치 행과 열을 대응한다. excluded_cells에는 미입력 표시·머리글·주석·계산 미저장 등 수치로 쓰면 안 되는 셀 좌표를 넣는다. 실제 0과 미입력, 실제 음수와 결측 표시를 문맥으로 구별한다. cached_sql_tables에 있는 동일 원문 표는 이미 검수했으므로 재출력하지 않는다. 원문 전체를 확인할 수 없는 표는 억지로 대응하지 않는다.
단위가 '%, 배'처럼 혼합되어 있으면 표 단위를 숫자에 그대로 붙이지 않는다. 각 행 의미를 검토하여 rows.unit에 '%' 또는 '배' 등 단일 단위를 지정하고 unit_quote에는 실제 혼합 단위 문구를 인용한다. 어느 단위인지 불명확하면 행 단위를 비워 검수 미완료로 남긴다.
SQL 조회 수치는 원문과 좌표 검사를 통과한 메타데이터에 따른 값이며 회계적 의미의 무오류를 보장하지 않는다. 원문과 충돌하면 원문을 재검토한다. SQL에 없는 수치가 원문에도 없다는 뜻은 아니다.'''


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def compact(packet):
    tables={}
    for row in packet.get('facts',[]):
        key=row['review_id']
        table=tables.setdefault(key,{'review_id':key[:12],'title':row['title'],'basis':row['basis'],
                                    'source_ids':row['source_ids'],'columns':['cell','metric','period','unit','value'],'rows':[]})
        table['rows'].append([row[k] for k in table['columns']])
    return {'retrieval':'parameterized_sql','tables':list(tables.values())}


def prompt_grids(grids, aliases):
    """Native sources already contain coordinates; other grids use compact rows."""
    result={}
    for alias,cells in grids.items():
        if aliases[alias].get('sheet') is not None:
            result[alias]={'coordinates':'sources.text의 A1=value 또는 R1C1=value. row는 행번호, column은 열문자 또는 C번호.'}
        else:
            result[alias]={'columns':['cell','row','column','raw'],
                           'rows':[[c[k] for k in ('cell','row','column','raw')] for c in cells]}
    return result


def budget_request(request, token_count):
    """Drop optional normalization work as whole source grids, never source text.

    Deferred originals still participate in assessment/generation; their DB
    normalization can be retried by a later scoped assessment.
    """
    body=json.loads(request['messages'][-1]['content'])
    deferred=[]
    def measure():
        request['messages'][-1]['content']=json.dumps(body,ensure_ascii=False,separators=(',',':'))
        return token_count(request['messages'])
    count,maximum=measure()
    while count+request['max_tokens']+512>maximum:
        grids=body.get('structured_grids',{})
        cached=body.get('cached_sql_tables',{})
        if grids:
            key=max(grids,key=lambda k:len(json.dumps(grids[k],ensure_ascii=False)))
            grids.pop(key);deferred.append(key)
        elif cached:
            cached.clear()  # Original sources and stored SQL facts remain intact.
        else:
            break  # Existing evidence recovery handles genuinely oversized originals.
        count,maximum=measure()
    allowed=list(body.get('structured_grids',{}))
    field=request['structured_outputs']['json']['properties']['structured_tables']
    if allowed:field['items']['properties']['source_id']['enum']=allowed
    else:field['maxItems']=0
    return {'input_tokens':count,'context_limit':maximum,'output_reserved':request['max_tokens'],
            'deferred_normalization_sources':deferred,'input_within_budget':count+request['max_tokens']+512<=maximum}


def number(raw):
    text = str(raw).strip()
    if ',' in text and not re.fullmatch(r'[+\-(]?\d{1,3}(?:,\d{3})+(?:\.\d+)?\)?',text):
        return None  # Footnote lists such as 5,38,40 are not an amount.
    text=text.replace(',', '')
    if re.fullmatch(r'\(\d+(?:\.\d+)?\)', text):
        text = '-' + text[1:-1]
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?', text):
        return None
    try:
        value = Decimal(text)
        return str(value) if value.is_finite() else None
    except InvalidOperation:
        return None


def grid(source):
    cells = []
    for line_no, line in enumerate(source['text'].splitlines(), 1):
        native = list(re.finditer(r'(?:^|\|\s*)([A-Z]{1,3})([1-9]\d*)=([^|]*)', line))
        legacy = list(re.finditer(r'(?:^|\|\s*)R(\d+)C(\d+)=([^|]*)', line))
        if native:
            parts = [(m[2], m[1], m[3].strip(), m[1]+m[2]) for m in native]
        elif legacy:
            parts = [(m[1], 'C'+m[2], m[3].strip(), 'R'+m[1]+'C'+m[2]) for m in legacy]
        else:
            # Delimited PDF/JSON/office tables only. Do not invent columns in prose.
            values = line.strip().strip('|').split('|') if '|' in line else line.strip().split('\t')
            if len(values) < 2:
                continue
            parts = [(str(line_no), str(i), v.strip(), f'L{line_no}C{i}') for i, v in enumerate(values, 1)]
        for row, column, raw, locator in parts:
            cells.append({'cell':locator, 'row':row, 'column':column, 'raw':raw, 'value':number(raw)})
    # Duplicate coordinates are ambiguous, even when a source joins page fragments.
    if len({c['cell'] for c in cells}) != len(cells):
        return []
    return cells


def extend_schema(schema, aliases, obj):
    text = {'type':'string'}
    table = obj({'source_id':{'type':'string','enum':list(aliases)}, 'title':text, 'title_quote':text,
                 'basis':text, 'basis_quote':text, 'unit':text, 'unit_quote':text,
                 'columns':{'type':'array','maxItems':12,'items':obj({'column':text,'period':text,'period_quote':text,'unit':text,'unit_quote':text})},
                 'rows':{'type':'array','maxItems':60,'items':obj({'row':text,'metric':text,'unit':text,'unit_quote':text})},
                 'excluded_cells':{'type':'array','items':text}})
    schema['properties']['structured_tables'] = {'type':'array','maxItems':12,'items':table}
    schema['required'].append('structured_tables')


def supported(value, quote, source):
    if not value:
        return True
    compact = lambda x: re.sub(r'[\s.,/\-년월일]', '', x)
    return bool(quote and quote in source and compact(value) in compact(quote))


class StructuredStore:
    def __init__(self, path, model):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.reviewer = digest([NORMALIZATION_VERSION, RULES, model])
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sources (hash TEXT PRIMARY KEY, document_id TEXT, source_id TEXT, raw_text TEXT);
                CREATE TABLE IF NOT EXISTS cells (source_hash TEXT, locator TEXT, row_id TEXT, column_id TEXT, raw TEXT, value TEXT, PRIMARY KEY(source_hash,locator));
                CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, source_hash TEXT, reviewer TEXT, metadata TEXT, status TEXT, reason TEXT);
                CREATE TABLE IF NOT EXISTS facts (review_id TEXT, locator TEXT, metric TEXT, period TEXT, unit TEXT, basis TEXT, value TEXT, PRIMARY KEY(review_id,locator));
                CREATE INDEX IF NOT EXISTS review_source ON reviews(source_hash,reviewer,status);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def source_hash(self, source):
        return digest([source['document_id'], source['id'], source['text'], source.get('sheet'), source.get('page')])

    def register(self, aliases):
        pending, cached = {}, {}
        with self.connect() as db:
            for alias, source in aliases.items():
                key = self.source_hash(source)
                cells = grid(source)
                db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?,?)', (key, source['document_id'], source['id'], source['text']))
                db.executemany('INSERT OR IGNORE INTO cells VALUES (?,?,?,?,?,?)',
                               [(key,c['cell'],c['row'],c['column'],c['raw'],c['value']) for c in cells])
                rows = self.query(db, source)
                if rows:
                    cached[alias] = rows
                # Completed coverage is explicit; partial tables stay eligible.
                covered = {r['cell'] for r in rows}
                for review in db.execute("SELECT metadata FROM reviews WHERE source_hash=? AND reviewer=? AND status='accepted'", (key,self.reviewer)):
                    metadata=json.loads(review['metadata'])
                    covered.update(metadata.get('excluded_cells',[]))
                    # Numeric year header cells are metadata, not observations.
                    periods={c['period'] for c in metadata.get('columns',[]) if c.get('period')}
                    covered.update(c['cell'] for c in cells if c['raw'] in periods)
                numeric = {c['cell'] for c in cells if c['value'] is not None}
                if numeric - covered:
                    pending[alias] = [{k:v for k,v in c.items() if k!='value'} for c in cells]
        return pending, cached

    def query(self, db, source):
        rows = db.execute('''SELECT f.locator AS cell, f.metric, f.period, f.unit, f.basis, f.value,
                            r.id AS review_id, r.metadata
                            FROM facts f JOIN reviews r ON r.id=f.review_id
                            WHERE r.source_hash=? AND r.reviewer=? AND r.status='accepted'
                            ORDER BY f.rowid''', (self.source_hash(source), self.reviewer)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item['title'] = json.loads(item.pop('metadata'))['title']
            item['source_ids'] = [source['id']]
            result.append(item)
        return result

    def review(self, tables, aliases):
        audit = []
        with self.connect() as db:
            for table in tables:
                source = aliases.get(table.get('source_id'))
                if source is None:
                    audit.append({'status':'rejected','reason':'unknown source'})
                    continue
                raw = source['text']; key = self.source_hash(source)
                metadata = {k:v for k,v in table.items() if k!='source_id'}
                identity = digest([key, self.reviewer, metadata])
                reason = ''
                if not table.get('title_quote') or table['title_quote'] not in raw:
                    reason = 'title provenance missing'
                for field in ('basis','unit'):
                    if not supported(table.get(field,''), table.get(field+'_quote',''), raw):
                        reason = field+' provenance mismatch'
                cells = grid(source)
                by_row = {}
                for cell in cells:
                    by_row.setdefault(cell['row'], []).append(cell)
                rows = table.get('rows',[]); columns = table.get('columns',[])
                if len({r['row'] for r in rows}) != len(rows) or len({c['column'] for c in columns}) != len(columns):
                    reason = 'duplicate coordinate mapping'
                facts = []
                for row in rows:
                    row_text = ' | '.join(c['raw'] for c in by_row.get(row['row'],[]))
                    if not row.get('metric') or row['metric'] not in row_text:
                        reason = 'row label provenance mismatch'; break
                    if not supported(row.get('unit',''),row.get('unit_quote',''),raw):
                        reason = 'row unit provenance mismatch'; break
                    # A tab-extracted PDF can omit note/blank cells per row. A
                    # shared column mapping is unsafe when selected rows differ.
                    widths={len(by_row.get(r['row'],[])) for r in rows}
                    if source.get('sheet') is None and len(widths)>1:
                        reason='ragged table requires explicit row-specific mapping'; break
                    for column in columns:
                        if not supported(column.get('period',''),column.get('period_quote',''),raw) or not supported(column.get('unit',''),column.get('unit_quote',''),raw):
                            reason = 'column metadata provenance mismatch'; break
                        unit = row.get('unit') or column.get('unit') or table.get('unit')
                        if not unit or re.search(r'[,，·/]| 및 ',unit) or not column.get('period'):
                            continue
                        for cell in by_row.get(row['row'],[]):
                            if cell['column']==column['column'] and cell['value'] is not None and cell['cell'] not in table.get('excluded_cells',[]):
                                facts.append((identity,cell['cell'],row['metric'],column['period'],unit,table.get('basis',''),cell['value']))
                status = 'rejected' if reason else ('accepted' if facts else 'unresolved')
                db.execute('INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?)', (identity,key,self.reviewer,json.dumps(metadata,ensure_ascii=False),status,reason))
                if status=='accepted':
                    # Never overwrite another interpretation; preserve conflicts for the LLM.
                    db.executemany('INSERT OR IGNORE INTO facts VALUES (?,?,?,?,?,?,?)', facts)
                audit.append({'review_id':identity,'source_id':source['id'],'status':status,'reason':reason,'fact_count':len(facts) if status=='accepted' else 0})
        return audit

    def packet(self, aliases):
        with self.connect() as db:
            rows = [row for source in aliases.values() for row in self.query(db,source)]
        return {'version':VERSION,'retrieval':'parameterized_sql','coverage':'selected delimited source tables; original evidence retained',
                'facts':rows,'fact_count':len(rows)}
