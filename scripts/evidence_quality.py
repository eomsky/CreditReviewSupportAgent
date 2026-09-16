"""Source-bound numeric observations and arithmetic assistance, not accounting inference."""
import copy
import math
import re

VERSION = 2
RULES = '''핵심 수치와 판단을 원문 기준으로 검증한다.
numeric_evidence의 role은 영업이익=operating_profit, 금융비용=finance_cost, 세전이익=pretax_profit, 법인세비용=income_tax, 당기순이익=net_profit이며 매출액·차입금·비중·배율 등 나머지는 other다. 항목명이 아니라 원문 정의를 확인하고 역할을 서로 구분한다. key_relationships.interest_coverage에는 numeric_evidence의 영업이익과 금융비용 인덱스를, earnings_bridge에는 세전이익·법인세·당기순이익 인덱스를 순서대로 기록한다. 근거 없는 관계만 빈 배열로 둔다.
numeric_evidence는 결론을 바꾸는 핵심 수치를 항목·기간·단위·연결/별도·조정기준과 함께 정리한다. quote는 해당 원문의 연속된 문구를 그대로 복사한다. 기준을 알 수 없으면 빈 문자열로 남기며 value는 확인 불가일 때 null이다. status는 confirmed/unknown/conflicting 중 선택한다. 같은 이름이라도 기간·범위·산식이 다른 값은 합치지 않는다.
calculations는 필요한 계산만 numeric_evidence의 0부터 시작하는 인덱스를 operands로 참조한다. operation은 ratio, growth_percent, sum, difference다. ratio는 분자/분모, growth_percent는 (당기/전기-1)*100, difference는 첫 값에서 나머지를 차감한다. scale은 산식 결과의 표시 배수다(배=1, %=100 등). 계산 가능성과 회계적으로 비교 가능함은 별개다. comparison_basis에 비교 가능한 근거를 설명하고 불명확하면 빈 문자열로 둔다.
배율과 %는 원문 단위와 분자·분모를 교차 확인한다. 모든 배율을 일률적으로 환산하지 않는다. 계산 결과는 보조 검증이며 원문을 대체하지 않는다.
0·음수·특정 분기만 연간합계와 같은 양식은 미입력/누적입력/실제실적을 원문 문맥으로 구별한다. 불명확하면 계절성·위험 부재·실제 0으로 단정하지 않는다.
적자 원인은 영업손익→영업외손익→세전손익→법인세→순손익을 대조한다. 단순 동반 증가를 인과로 단정하지 않는다. 담보 여력에는 선순위·평가액·설정액, 자산의 질에는 회수·연령·충당금 근거가 필요하다.
자료 우선순위만으로 기준 충돌을 해소하지 않는다. 연결/별도·기간·조정 전후·집계 범위를 확인한 뒤 선택 근거를 설명한다. 원문을 찾지 못한 상태와 위험이 없다고 확인한 상태를 구별한다.
'''


RULES+='\n판단 제한: 상세표/요약표 중 상세표라는 이유만으로 배율 단위를 확정하지 않는다. 분자÷분모와 표시 배율이 충돌하면 단위 오류 가능성을 명시하고 높다/낮다 판단을 보류하거나 산식으로 확인된 기준을 명시해 정정한다. 연간합계가 특정 분기에만 입력되고 다른 분기가 0이면 그 표만으로 계절성을 확정할 수 없다. 실제 분기 실적이라는 별도 근거 없이는 집중 발생 표현을 삭제하고 분기별 실적 미확인으로 수정한다. 세전 흑자·세후 적자이면 세전 수익성 악화 원인과 법인세 반영 후 적자 전환을 구분하여 반드시 설명한다. 이 판단 제한은 자료 우선순위로 값을 선택하라는 다른 지침보다 우선한다.'

def extend_schema(schema, refs, obj):
    text={'type':'string'}
    schema['properties']['numeric_evidence']={'type':'array','maxItems':16,'items':obj({
        'metric':text,'period':text,'unit':text,'basis':text,
        'role':{'type':'string','enum':['operating_profit','finance_cost','pretax_profit','income_tax','net_profit','other'],
                'description':'원문 문맥에서 이 수치의 회계적 역할을 판단한다. 이름이 비슷해도 정의가 다르면 other.'},
        'value':{'type':['number','null']},'status':{'type':'string','enum':['confirmed','unknown','conflicting']},
        'quote':text,'source_ids':refs})}
    schema['properties']['calculations']={'type':'array','maxItems':6,'items':obj({
        'metric':text,'operation':{'type':'string','enum':['ratio','growth_percent','sum','difference']},
        'operands':{'type':'array','minItems':2,'maxItems':6,'items':{'type':'integer','minimum':0,'maximum':15}},
        'scale':{'type':'number'},'comparison_basis':text})}
    schema['required']+=['numeric_evidence','calculations']
    schema['properties']['key_relationships']=obj({
        name:{'type':'array','maxItems':count,'items':{'type':'integer','minimum':0,'maximum':15},
              'description':description+' numeric_evidence 인덱스. 필요한 원문 수치를 numeric_evidence에 먼저 포함한다. 근거가 없으면 빈 배열.'}
        for name,count,description in (
            ('interest_coverage',2,'동일 기간·단위·기준의 영업이익, 금융비용 순서'),
            ('earnings_bridge',3,'동일 기간·단위·기준의 세전이익, 법인세비용, 당기순이익 순서'))})
    schema['required'].append('key_relationships')


def validate(packet, sources):
    result=copy.deepcopy(packet)
    rows=result.get('numeric_evidence',[])
    for row in rows:
        refs=row.get('source_ids',[])
        quote=row.get('quote','')
        # A trailing citation decoration is not part of the quoted source.
        candidate=re.sub(r'\s*\(S\d+[^\n]*\)\s*$','',quote)
        if refs and any(s in sources and candidate and candidate in sources[s]['text'] for s in refs):
            quote=candidate
            row['quote']=quote
        row['source_verified']=bool(quote and refs and all(s in sources for s in refs)
                                    and any(quote in sources[s]['text'] for s in refs))
        # Check lexical numeric support; accounting meaning is still reviewed by the LLM.
        if row.get('value') is not None:
            numbers=[float(x.replace(',','')) for x in re.findall(r'-?\d[\d,]*(?:\.\d+)?',quote)]
            row['source_verified']=row['source_verified'] and row['value'] in numbers
        if not row['source_verified']:
            row['status']='unknown'
            row['value']=None
    checks=[]
    groups={}
    for i,row in enumerate(rows):
        group=(row.get('period'),row.get('unit'),row.get('basis'))
        groups.setdefault(group,{}).setdefault(row.get('role','other'),[]).append(i)
    for roles in groups.values():
        for name,operation,needed in (
                ('영업이익/금융비용 (배)','ratio',('operating_profit','finance_cost')),
                ('세전이익-법인세 (동일 원문 단위)','difference',('pretax_profit','income_tax'))):
            if all(len(roles.get(role,[]))==1 for role in needed):
                result.setdefault('calculations',[]).append({'metric':name,'operation':operation,
                    'operands':[roles[role][0] for role in needed],'scale':1,
                    'comparison_basis':'LLM이 원문에서 분류한 회계 항목, 동일 기간·단위·기준'})
    for name,indices in result.get('key_relationships',{}).items():
        count=2 if name=='interest_coverage' else 3
        if len(indices)!=count:continue
        result.setdefault('calculations',[]).append({
            'metric':name,'operation':'ratio' if count==2 else 'difference',
            'operands':indices[:2],'scale':1,
            'comparison_basis':'LLM이 연결한 원문 항목: 단위·기간·기준과 원문 산식을 함께 대조할 것'})
    for calculation in result.get('calculations',[]):
        check={**calculation,'result':None,'status':'unresolved'}
        indices=calculation.get('operands',[])
        valid=all(type(i) is int and 0<=i<len(rows) for i in indices)
        operands=[rows[i] for i in indices] if valid else []
        op=calculation['operation']
        compatible=bool(operands and len({r.get('unit') for r in operands})==1
                        and len({r.get('basis') for r in operands})==1
                        and (op=='growth_percent' or len({r.get('period') for r in operands})==1))
        if compatible and calculation.get('comparison_basis') and all(
                r.get('source_verified') and r.get('status')=='confirmed'
                and all(r.get(k) for k in ('period','unit','basis'))
                and type(r.get('value')) in (int,float) and math.isfinite(r['value']) for r in operands):
            values=[r['value'] for r in operands];op=calculation['operation']
            value=None
            if op in ('ratio','growth_percent') and len(values)==2 and values[1]!=0:
                value=values[0]/values[1]
                if op=='growth_percent':value=(value-1)*100
            elif op=='sum':value=sum(values)
            elif op=='difference':value=values[0]-sum(values[1:])
            if value is not None and math.isfinite(value*calculation['scale']):
                check.update(result=value*calculation['scale'],status='arithmetic_only')
        checks.append(check)
    result['arithmetic_checks']=checks
    result['quality_version']=VERSION
    return result


def context(packet):
    from runtime_structured_store import compact
    result={k:packet.get(k,[]) for k in ('facts','conflicts','numeric_evidence','arithmetic_checks')}
    result['structured_sql']=compact(packet.get('structured_sql',{}))
    return result


def merge(packets):
    result={k:[] for k in ('facts','conflicts','numeric_evidence','arithmetic_checks','source_excerpts')}
    valid=bool(packets) and all(p.get('quality_version')==VERSION for p in packets)
    for packet in packets:
        offset=len(result['numeric_evidence'])
        for key in result:
            rows=copy.deepcopy(packet.get(key,[]))
            if key=='arithmetic_checks':
                for row in rows:row['operands']=[i+offset for i in row['operands']]
            result[key].extend(rows)
    if valid:result['quality_version']=VERSION
    sql=[p.get('structured_sql',{}) for p in packets]
    if any(sql):
        unique={}
        for item in sql:
            for row in item.get('facts',[]):unique[(row['review_id'],row['cell'])]=row
        result['structured_sql']={'retrieval':'parameterized_sql','facts':list(unique.values()),'fact_count':len(unique)}
    return result
