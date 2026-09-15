"""Candidate transport: explicit earnings roles before other numeric observations."""
import ast


def patch(source):
    marker="    identity={'version':VERSION"
    assert source.count(marker)==1
    injection='''    earnings_slots = previous_packet is None and name in ('financial_accounts','profitability')
    if earnings_slots:
        slot_roles=('operating_profit','finance_cost','pretax_profit','income_tax','net_profit')
        item=schema['properties']['numeric_evidence']['items']
        slot_props={}
        for role in slot_roles:
            role_item=copy.deepcopy(item)
            role_item['properties']['role']['enum']=[role]
            slot_props['latest_actual_'+role]={'type':'array','maxItems':1,'items':role_item,
                'description':'최신 실적의 동일 기간·기준 해당 수치. 원문 확인 불가이면 빈 배열. 단순 항목명 유사성으로 다른 계정을 대입하지 않는다.'}
        slot_props['other']={'type':'array','maxItems':11,'items':item}
        schema['properties']['numeric_evidence']=obj(slot_props)
        refs=list(slot_props)[:-1]+['other_'+str(i) for i in range(11)]
        schema['properties']['calculations']['items']['properties']['operands']['items']={'type':'string','enum':refs}
        del schema['properties']['key_relationships']
        schema['required'].remove('key_relationships')
        rules+='\\n전송 구조 최종 규칙: latest_actual_ 항목은 원문에서 확인되는 가장 최근의 실제 결산기간 수치다. 표의 첫 숫자 열이나 추정기간을 고르지 않는다. 다섯 항목을 동일한 최신 실제기간·기준으로 먼저 검토하며 해당 기간의 원문이 없을 때만 빈 배열로 남긴다. other는 과거 비교 및 나머지 핵심 수치다. calculations.operands에는 숫자 인덱스 대신 latest_actual_pretax_profit 같은 위 필드 이름 또는 other_0 같은 other 위치를 쓴다. key_relationships는 반환하지 않는다. 프로그램이 역할·기간·단위가 일치하는 경우에만 기본 산술을 보조 검증한다. 원문 역할을 추론하되 찾지 못한 값은 만들어내지 않는다.'
'''
    source=source.replace(marker,injection+marker)
    marker='    packet=restore_assessment_references(packet,previous)'
    assert source.count(marker)==1
    restore='''    if earnings_slots:
        slots=packet['numeric_evidence'];flat=[];addresses={}
        for role in slot_roles:
            key='latest_actual_'+role
            if slots[key]:addresses[key]=len(flat);flat.extend(slots[key])
        for i,item in enumerate(slots['other']):addresses['other_'+str(i)]=len(flat);flat.append(item)
        for calculation in packet['calculations']:
            if any(address not in addresses for address in calculation['operands']):raise ValueError('계산이 미확인 수치를 참조함')
            calculation['operands']=[addresses[address] for address in calculation['operands']]
        packet['numeric_evidence']=flat
        packet['key_relationships']={'interest_coverage':[],'earnings_bridge':[]}
'''
    source=source.replace(marker,restore+marker)
    ast.parse(source)
    return source
