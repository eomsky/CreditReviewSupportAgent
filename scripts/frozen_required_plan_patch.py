"""Equivalent table-plan capacity with structurally mandatory requested sections."""
import ast

def patch(source):
    marker="    identity={'version':VERSION"
    extra='''    if outline and not fixed:
        required_plans={}
        for title in titles:
            scoped=copy.deepcopy(plan)
            scoped['properties']['section']['enum']=[title]
            required_plans[title]=scoped
        del schema['properties']['tables']
        schema['required'].remove('tables')
        schema['properties']['required_tables']=obj(required_plans)
        schema['properties']['additional_tables']={'type':'array','maxItems':len(titles),'items':plan}
        schema['required']+=['required_tables','additional_tables']
        rules+='\\n요청된 각 중분류의 첫 표를 required_tables의 해당 이름에 설계한다. 추가 표가 필요한 경우만 additional_tables에 반환한다. 기존 내용·근거·행·열 설계 지침을 그대로 준수한다.'
'''
    assert source.count(marker)==1
    source=source.replace(marker,extra+marker)
    marker="    packet=evidence_quality.validate(packet,"
    extra="""    if outline and not fixed:
        primary=packet.pop('required_tables')
        packet['tables']=[primary[title] for title in titles]+packet.pop('additional_tables')
"""
    assert source.count(marker)==1
    source=source.replace(marker,extra+marker)
    ast.parse(source)
    return source
