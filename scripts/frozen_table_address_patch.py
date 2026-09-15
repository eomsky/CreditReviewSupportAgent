"""Keep fixed cells unchanged structurally; expose semantic labels in edit addresses."""
import ast

HELPERS='''
def labelled_addresses(fields,tables):
    for ti,table in enumerate(tables):
        header=fields[f'T{ti}']['properties']['columns']
        possible=header['items']['enum']
        positions={}
        for ci,original in enumerate(table['columns']):
            choices=[original]
            if not table.get('fixed_template') and isinstance(original,str) and re.search(r'20\\d{2}',original):
                skeleton=re.sub(r'20\\d{2}','YEAR',original)
                choices += [h for h in possible if isinstance(h,str) and re.sub(r'20\\d{2}','YEAR',h)==skeleton]
            positions[f'C{ci}']={'type':['string','null'],'enum':list(dict.fromkeys(choices))}
        fields[f'T{ti}']['properties']['columns']={'type':'object','properties':positions,'required':list(positions),'additionalProperties':False}
        rows=fields[f'T{ti}']['properties']['rows']
        named={}
        for ri,row in enumerate(table['rows']):
            spec=rows['properties'][f'R{ri}']
            values=spec['properties']['values']
            values['properties']={f'{key}::{table["columns"][int(key[1:])]}':value for key,value in values['properties'].items()}
            values['required']=[]
            named[f'R{ri}::{row[0] if row and row[0] else "미사용 양식 행"}']=spec
        rows['properties']=named;rows['required']=list(named)
    return fields

def plain_addresses(result):
    for table in result.values():
        if isinstance(table['columns'],dict):
            table['columns']=[table['columns'][f'C{i}'] for i in range(len(table['columns']))]
        rows={}
        for key,row in table['rows'].items():
            index=key.split('::',1)[0]
            if index in rows:raise ValueError('중복된 표 행 주소')
            values={}
            for address,value in row['values'].items():
                column=address.split('::',1)[0]
                if column in values:raise ValueError('중복된 표 열 주소')
                values[column]=value
            rows[index]={**row,'values':values}
        table['rows']=rows
    return result

def plain_stream(text):
    return re.sub(r'"([RC]\\d+)::(?:\\\\.|[^"\\\\])*"(?=\\s*:)',lambda m:'"'+m.group(1)+'"',text)

'''

def patch(source):
    # Keep transport adaptation separate from source-value validation and layout.
    source=source.replace('def schema(tables,ids,years=None):',HELPERS+'def schema(tables,ids,years=None):',1)
    assert source.count('    return obj(fields)')==1
    source=source.replace('    return obj(fields)','    return obj(labelled_addresses(fields,tables))')
    source=source.replace('for cell in stream_cells(text,keys):','for cell in stream_cells(plain_stream(text),keys):')
    source=source.replace("result=json.loads(response['choices'][0]['message']['content']);audit=[]", "result=plain_addresses(json.loads(response['choices'][0]['message']['content']));audit=[]")
    source=source.replace("'content':RULES+'\\n'+evidence_quality.RULES", "'content':RULES+'\\n'+evidence_quality.RULES+'\\n응답의 행·열 키에는 실제 항목명과 대상 기간이 포함되어 있다. 각 변경값은 그 키에 명시된 기간·항목에 해당해야 한다. 원문에 두 기간만 있으면 표의 첫 두 숫자 열에 순서대로 넣지 말고 같은 기간의 키에만 대응한다. 원문 머리글이 없는 발췌에 다른 표의 기간을 차용하지 않는다. 동일 이름이라도 정의·산식이 다르면 기존 지표를 다른 지표로 대체하지 말고 충돌을 설명한다.'")
    ast.parse(source)
    return source
