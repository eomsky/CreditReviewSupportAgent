"""Reuse prior assessed records losslessly during incremental source assessment."""
import ast

HELPERS = '''
def assessment_reference_schema(schema, previous):
    if previous is None:return
    for field in ('numeric_evidence','tables'):
        records=previous.get(field,[])
        spec=schema['properties'].get(field)
        if not records or not spec or spec.get('maxItems')==0:continue
        original=spec['items']
        spec['items']={'anyOf':[{
            'type':'object','properties':{'previous_index':{
                'type':'integer','minimum':0,'maximum':len(records)-1}},
            'required':['previous_index'],'additionalProperties':False},original]}

def restore_assessment_references(packet, previous):
    for field in ('numeric_evidence','tables'):
        restored=[]
        for record in packet.get(field,[]):
            if 'previous_index' not in record:
                restored.append(record);continue
            index=record['previous_index']
            records=(previous or {}).get(field,[])
            if type(index) is not int or not 0<=index<len(records):
                raise ValueError('Invalid prior assessment reference')
            item=copy.deepcopy(records[index])
            if field=='numeric_evidence':item['_prior_quote_restored']=True
            restored.append(item)
        packet[field]=restored
    return packet

'''

def patch(source):
    marker='def obj(props):'
    assert source.count(marker)==1
    source=source.replace(marker,HELPERS+marker,1)
    marker="    identity={'version':VERSION"
    assert source.count(marker)==1
    source=source.replace(marker,"    assessment_reference_schema(schema,previous_packet)\n    if previous_packet is not None:\n        rules+='\\n추가 자료 검토에서는 기존 numeric_evidence 또는 tables 기록이 그대로 유효하면 previous_index(각 배열의 0부터 시작하는 인덱스)만 반환한다. 프로그램이 근거와 값·기간·단위·열·행을 손실 없이 복원한다. 새 근거로 수정하거나 추가할 기록은 기존 전체 형식으로 반환한다. 최종 배열은 유지할 기존 참조와 수정·신규 기록으로 구성하고, calculations 인덱스는 이 최종 numeric_evidence 배열을 가리킨다. 기존 인용 원문은 다시 L번호로 추정하지 않는다. 새 sources에 예전 정보가 없다는 이유로 확인된 표 열을 삭제하지 않는다.'\n"+marker)
    marker='    packet=restore_quote_spans(packet,aliases)'
    assert source.count(marker)==1
    source=source.replace(marker,'    packet=restore_assessment_references(packet,previous)\n'+marker)
    marker="    for row in packet.get('numeric_evidence',[]):\n        span=row.pop('quote_span',{})"
    assert source.count(marker)==1
    source=source.replace(marker,"    for row in packet.get('numeric_evidence',[]):\n        if row.pop('_prior_quote_restored',False):continue\n        span=row.pop('quote_span',{})")
    ast.parse(source)
    return source
