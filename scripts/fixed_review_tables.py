"""Fixed review layouts extracted from the user supplied workbook; no sample values."""
import json
from pathlib import Path
TEMPLATES=json.loads((Path(__file__).resolve().parents[1]/'prompts/fixed_review_tables.json').read_text(encoding='utf-8'))

def configure(schema, view):
    templates=TEMPLATES.get(view)
    if not templates:return ''
    props={}
    for i,t in enumerate(templates):
        width=len(t['columns'])-(0 if t['customer'] else 1)
        row={'type':'array','items':{'type':['number','string','null'] if t['customer'] else ['number','null']},'minItems':width,'maxItems':width}
        count=2 if t['customer'] else 3
        fields={'periods':{'type':'array','items':{'type':'string'},'minItems':count,'maxItems':count,'description':'전기, 당기 순서의 두 기간' if t['customer'] else '전전기, 전기, 당기 순서의 세 기간'}}
        fields.update({f'r{j}':row for j in range(len(t['labels']))})
        props[f't{i}']={'type':'object','properties':fields,'required':list(fields),'additionalProperties':False}
    schema['properties']['fixed_tables']={'type':'object','properties':props,'required':list(props),'additionalProperties':False}
    schema['required']=list(schema['required'])+['fixed_tables']
    return '\n고정 표 입력 규칙: '+json.dumps(templates,ensure_ascii=False)+'\nfixed_tables의 t0,t1 순서로 각 표를 채운다. 일반 표의 periods는 원문 기준 전전기, 전기, 당기 순서의 세 기간이다. 매출처 표의 periods는 전기, 당기 순서의 두 기간만 반환한다. 기간은 과거부터 최근 순서로 중복 없이 작성한다. 빈값은 JSON null이며 문자열 null을 쓰지 않는다. r0부터 labels 순서의 행이다. 일반 표는 행명 제외 숫자 열만 반환한다. 매출처 표는 전기 매출처명/금액/비중, 당기 매출처명/금액/비중 6개 열을 반환한다. 상기 외와 합계 행은 유지한다. 원자료의 단위에 맞춰 표 단위로 환산한다. 확인 안 되는 값은 null. 추정1기와 동업계평균은 실제 자료가 있을 때만 채운다. 표 행을 추가, 삭제, 재배열하지 않는다. 매출처 합계만 확인되고 구성내역이 없으면 빈 상세 행 하나에 매출처별 내역 미확인이라는 설명과 확인된 합계액·비중을 표시한다. 이는 실제 거래처명이 아닌 미확인 구성내역의 표시다. 일부 내역만 확인되면 같은 기준의 합계와 상세액 차이를 원문에 근거해 판단하여 미확인 내역으로 구분한다. 미사용 빈 행을 0으로 채우지 않는다. 상세내역과 합계가 일관되는지 확인한다.'

def apply(result,view):
    templates=TEMPLATES.get(view)
    if not templates:return
    values=result.pop('fixed_tables',{})
    tables=[]
    for i,t in enumerate(templates):
        data=values.get(f't{i}',{});periods=data.get('periods',[])
        if len(periods)!=(2 if t['customer'] else 3):raise ValueError('고정 표 기간 누락')
        columns=list(t['columns'])
        if t['customer']:columns[1]=periods[0]+' 금액';columns[4]=periods[1]+' 금액'
        else:columns[1:4]=periods
        rows=[]
        for j,label in enumerate(t['labels']):
            cells=data.get(f'r{j}')
            if not isinstance(cells,list) or len(cells)!=len(columns)-(0 if t['customer'] else 1):raise ValueError('고정 표 행 또는 열 누락')
            cells=[None if isinstance(v,str) and v.strip()=='null' else v for v in cells]
            if t['customer'] and j>=5:cells[0]=label;cells[3]=label
            rows.append(cells if t['customer'] else [label]+cells)
        tables.append({'caption':t['caption'],'columns':columns,'rows':rows,'after_paragraph_index':-1,'fixed_template':True})
    result['tables']=tables
