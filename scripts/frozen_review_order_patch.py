"""Evaluate each required quality dimension before choosing paragraph edits."""
import ast

def patch(source):
    old="    schema['required'].append('quality_checks')\n    return schema"
    assert source.count(old)==1
    new="""    check=schema['properties'].pop('quality_checks')['items']
    categories=check['properties'].pop('category')['enum']
    check['required'].remove('category')
    checks=obj({category:copy.deepcopy(check) for category in categories})
    schema['properties']={'quality_checks':checks,**schema['properties']}
    schema['required']=list(schema['properties'])
    return schema"""
    source=source.replace(old,new)
    old="    parsed=remap_ids(json.loads(choice['message']['content']),original_ids)"
    assert source.count(old)==1
    source=source.replace(old,old+"\n    parsed['quality_checks']=[{'category':category,**value} for category,value in parsed['quality_checks'].items()]")
    old="    system=with_reasoning(system)"
    assert source.count(old)==1
    source=source.replace(old,"    system+='\\n출력 순서: quality_checks의 네 범주를 먼저 대조하고 그 결과에 따라 revisions/additions를 작성한다. reason에는 점검했다는 선언 대신 실제 대조한 항목·기간·단위·산식이나 모순을 짧게 기록한다. 단순 수식어 수정은 수치·인과 검증이 아니다. 배수 판단은 가능한 경우 분자/분모로 확인한다. 손익 전환 원인은 영업외손익과 세전손익·법인세·순손익의 관계를 구분하고, 필요한 원문을 찾지 못하면 직접 원인으로 단정하지 않는다. corrected로 판정한 문제는 관련 모든 문단을 실제로 수정한다. 근거가 없는 위험 부재 표현은 unresolved로 판단하고 문단의 단정도 완화한다.'\n"+old)
    ast.parse(source)
    return source
