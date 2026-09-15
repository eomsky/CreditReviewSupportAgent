"""Plan one record per row rather than a flat list of cell contents."""
import ast

HELPERS='''
def record_plan_schema(node):
    if isinstance(node,list):
        for item in node:record_plan_schema(item)
    elif isinstance(node,dict):
        props=node.get('properties',{})
        if 'row_labels' in props:
            original=props.pop('row_labels');node['required'].remove('row_labels')
            props['row_records']={**original,'description':'표의 한 행이 나타내는 대상별로 한 객체. 셀 값을 펼쳐서 행으로 만들지 않는다.','items':obj({'record_identity':{'type':'string','description':'이 한 행을 구별하는 기업·기간·사업부문·측정항목 등의 조합. 열마다 별도 객체를 만들지 않는다.'},'label':{'type':'string','description':'그 행의 첫 번째 열 값만. 나머지 열의 금액·기간·비율을 이 목록의 다음 행으로 나열하지 않는다.'}})}
            node['required'].append('row_records')
        for value in list(node.values()):record_plan_schema(value)

def row_identity(table,index,label):
    records=table.get('row_records',[])
    return records[index]['record_identity'] if index<len(records) else label

'''

def patch(source):
    source=source.replace('def obj(props):',HELPERS+'def obj(props):',1)
    marker="    identity={'version':VERSION"
    assert source.count(marker)==1
    source=source.replace(marker,"    record_plan_schema(schema)\n    rules+='\\n표 계획은 row_records로 반환한다. record_identity에서 한 행의 대상과 기간 등 식별 기준을 먼저 정하고 label에는 그 행의 첫 열 값만 쓴다. 가로 셀들을 세로 행 목록으로 펼치지 않는다. 같은 첫 열 값이 반복돼도 기간·대상이 다르면 record_identity로 구별한다. 기존 행·열 설계와 근거 검토 역할은 유지한다.'\n"+marker)
    marker='    packet=evidence_quality.validate(packet,'
    assert source.count(marker)==1
    source=source.replace(marker,"    for table in packet.get('tables',[]):table['row_labels']=[record['label'] for record in table['row_records']]\n"+marker)
    source=source.replace("f'{label} 행의 {c} 열", "f'{row_identity(t,j,label)} 행의 {c} 열")
    source=source.replace("f'첫 열은 이미 {label}로 지정되었다.", "f'행 식별: {row_identity(t,j,label)}. 첫 열은 이미 {label}로 지정되었다.")
    ast.parse(source)
    return source
