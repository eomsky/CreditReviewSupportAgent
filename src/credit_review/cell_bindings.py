"""LLM selects semantic cells; Python copies their unchanged literal values."""
from decimal import Decimal
import re
from typing import Literal
from pydantic import Field
from .models import Model, DatasetCalculation, Dataset


class CellRef(Model):
    source_id: str
    row: int = Field(ge=0)
    column: int = Field(ge=0)


class BoundColumn(Model):
    name: str
    dtype: Literal['string','number','integer','boolean']
    unit: str | None = None
    description: str = ''
    cells: list[CellRef] = Field(min_length=1,max_length=3)


class BoundFoundation(Model):
    entity: str
    scope: Literal['CONSOLIDATED','SEPARATE','UNKNOWN']
    period_column: str
    columns: list[BoundColumn] = Field(min_length=1,max_length=8)
    after_dataset: DatasetCalculation | None = None
    limitations: list[str] = Field(default_factory=list)


def markdown_cells(text):
    rows=[]
    for line in text.splitlines():
        line=line.strip()
        if not line.startswith('|') or not line.endswith('|'):
            continue
        cells=[cell.strip().replace('\\|','|') for cell in re.split(r'(?<!\\)\|',line[1:-1])]
        if all(re.fullmatch(r':?-{2,}:?',cell.replace(' ','')) for cell in cells):
            continue
        rows.append(cells)
    return rows


def index_tables(context):
    """No additional copy of cell bodies is added to the prompt."""
    from copy import deepcopy
    indexed=deepcopy(context)
    matrices={}
    for sid,source in indexed['sources'].items():
        if source.get('kind')!='table':
            continue
        matrix=markdown_cells(source.get('text',''))
        if not matrix: continue
        matrices[sid]=matrix
        source['text']='\n'.join('r'+str(i)+' | '+' | '.join('c'+str(j)+'='+v for j,v in enumerate(row))
                                 for i,row in enumerate(matrix))
        source['cell_addressing']='Zero-based r=row and c=column; r0 is the original header. Use exact cell addresses.'
    return indexed,matrices


def literal_value(text,dtype):
    if dtype=='string': return text
    if dtype=='boolean':
        if text.lower() in {'true','false'}: return text.lower()=='true'
        raise ValueError('Selected cell is not a boolean')
    if text.strip() in {'','-','—','–','N/A'}: return None
    literal=text.strip().replace(',','').replace('−','-')
    negative=literal.startswith('(') and literal.endswith(')')
    if negative: literal=literal[1:-1]
    if not re.fullmatch(r'[+-]?\d+(?:\.\d+)?',literal):
        raise ValueError('Selected numeric cell contains nonnumeric text: '+text[:80])
    number=Decimal(literal)*(-1 if negative else 1)
    if dtype=='integer' and number!=number.to_integral_value():
        raise ValueError('Selected integer cell has a fractional value')
    return int(number) if number==number.to_integral_value() else float(number)


def materialize(bound,matrices):
    count=len(bound.columns[0].cells)
    if any(len(column.cells)!=count for column in bound.columns):
        raise ValueError('Every selected column must cover the same periods')
    rows=[{} for _ in range(count)]
    refs=[{} for _ in range(count)]
    for column in bound.columns:
        for i,cell in enumerate(column.cells):
            if cell.source_id not in matrices:
                raise ValueError('Cell reference must identify a loaded table')
            matrix=matrices[cell.source_id]
            if cell.row>=len(matrix) or cell.column>=len(matrix[cell.row]):
                raise ValueError('Selected table cell is out of bounds')
            rows[i][column.name]=literal_value(matrix[cell.row][cell.column],column.dtype)
            refs[i][column.name]=[cell.source_id]
    return Dataset(name='공통 재무자료',description='LLM-selected source cells copied without arithmetic',
                   entity=bound.entity,scope=bound.scope,value_type='ACTUAL',period_column=bound.period_column,
                   columns=[{'name':c.name,'dtype':c.dtype,'unit':c.unit,'description':c.description} for c in bound.columns],
                   rows=rows,cell_sources=refs)
