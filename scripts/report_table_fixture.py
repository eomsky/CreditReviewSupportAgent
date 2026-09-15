"""Extract a labelled workbook block without shifting sparse column positions."""
import hashlib
import io
import re
import sqlite3
import openpyxl

def extract(raw, sheet_name, caption, year, database):
    book=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
    sheet=book[sheet_name]
    rows=list(sheet.iter_rows())
    start=next(i for i,row in enumerate(rows) if any(str(c.value or '').startswith(caption) for c in row))
    title=next(str(c.value) for c in rows[start] if str(c.value or '').startswith(caption))
    labels={str(c.value):c.column-1 for c in rows[start+1] if c.value is not None}
    keys=['업체명',f'{year} 거래대금',f'{year} 비중']
    indexes=[labels[k] for k in keys]
    extracted=[];cells=[]
    for row in rows[start+2:]:
        if any(str(c.value or '').startswith('[') for c in row):break
        if row[indexes[0]].value is None:continue
        values=[row[i].value for i in indexes]
        if any(v is None for v in values):raise ValueError('Incomplete source row')
        extracted.append(values);cells.append([row[i].coordinate for i in indexes])
    if not extracted:raise ValueError('No source rows')
    db=sqlite3.connect(database)
    db.execute('CREATE TABLE IF NOT EXISTS facts (source_hash TEXT, sheet TEXT, block TEXT, year INTEGER, ordinal INTEGER, name TEXT, amount REAL, share REAL, PRIMARY KEY(source_hash,sheet,block,year,ordinal))')
    digest=hashlib.sha256(raw).hexdigest()
    db.executemany('INSERT OR IGNORE INTO facts VALUES(?,?,?,?,?,?,?,?)',[(digest,sheet_name,caption,year,i,*r) for i,r in enumerate(extracted)])
    db.commit()
    result=db.execute('SELECT name,amount,share FROM facts WHERE source_hash=? AND sheet=? AND block=? AND year=? ORDER BY ordinal',(digest,sheet_name,caption,year)).fetchall()
    db.close()
    assert [list(r) for r in result]==extracted
    return {'columns':keys,'rows':[list(r) for r in result]}, {'sha256':digest,'sheet':sheet_name,'caption':title,'cells':cells,'year':year,'unit':re.search(r'단위:\s*([^)]*)',title).group(1),'normalization':'none; original units retained','sql_roundtrip_exact':True}
