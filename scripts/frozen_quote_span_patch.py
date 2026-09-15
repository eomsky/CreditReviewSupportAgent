"""Lossless source quote references instead of repeated generated quotation text."""
import ast

HELPERS='''
def numbered_source(text):
    return '\\n'.join(f'L{i:04d} {line}' for i,line in enumerate(text.split('\\n'),1))

def restore_quote_spans(packet, aliases):
    for row in packet.get('numeric_evidence',[]):
        span=row.pop('quote_span',{})
        sid=span.get('source_id');a=span.get('start_line');b=span.get('end_line')
        row['quote']=''
        if sid not in aliases or sid not in row.get('source_ids',[]):continue
        lines=prompt_source_text(aliases[sid]).split('\\n')
        if type(a) is int and type(b) is int and 1<=a<=b<=len(lines):
            row['quote']='\\n'.join(lines[a-1:b])
    return packet

'''

def patch(source):
    source=source.replace('def obj(props):',HELPERS+'def obj(props):',1)
    marker="    identity={'version':VERSION"
    extra='''    numeric=schema['properties']['numeric_evidence']['items']
    numeric['properties'].pop('quote');numeric['required'].remove('quote')
    maximum=max((len(prompt_source_text(s).split('\\n')) for s in aliases.values()),default=1)
    numeric['properties']['quote_span']=obj({'source_id':{'type':'string','enum':list(aliases)},'start_line':{'type':'integer','minimum':1,'maximum':maximum},'end_line':{'type':'integer','minimum':1,'maximum':maximum}})
    numeric['required'].append('quote_span')
    rules+='\\n전송 형식 최종 규칙: numeric_evidence의 quote 원문을 반복 출력하는 대신 quote_span에 source_id와 원문의 L번호 start_line/end_line을 선택한다. 프로그램이 해당 연속 행을 원문 그대로 복원한다. 수치가 있는 최소한의 연속 행을 선택하고 원문 전체 범위를 불필요하게 지정하지 않는다. 선택한 원문은 source_ids에 포함한다. 수치·기간·단위·기준 판별과 필요한 numeric_evidence 개수는 그대로 유지한다. L번호는 위치 표시이므로 value나 source_excerpts의 passages에 복사하지 않는다. source_excerpts는 L번호를 제외한 실제 원문만 복사한다.'
'''
    assert source.count(marker)==1
    source=source.replace(marker,extra+marker)
    old="'text':prompt_source_text(s)} for k,s in aliases.items() if previous_packet"
    assert source.count(old)==1
    source=source.replace(old,"'text':numbered_source(prompt_source_text(s))} for k,s in aliases.items() if previous_packet")
    marker='    packet=evidence_quality.validate(packet,'
    assert source.count(marker)==1
    source=source.replace(marker,'    packet=restore_quote_spans(packet,aliases)\n'+marker)
    ast.parse(source)
    return source
