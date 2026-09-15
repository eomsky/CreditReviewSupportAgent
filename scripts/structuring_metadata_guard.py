"""Carry unresolved source metadata into final guidance, preserving model audit."""
import copy,json

def apply(result,evidence):
    output=copy.deepcopy(result)
    used={s['id'] for p in output.get('paragraphs',[]) for s in p.get('sources',[])}
    unknown=[]
    for source in evidence:
        if source['id'] not in used:continue
        try:table=json.loads(source['text'])
        except (ValueError,TypeError):continue
        if table.get('basis') in (None,'unknown') and table.get('table_id'):unknown.append(source['id'])
    if not unknown:return output
    refinement=output.setdefault('refinement',{})
    refinement.setdefault('model_quality_checks',copy.deepcopy(refinement.get('quality_checks',[])))
    notice='사용된 표의 연결·별도 작성 기준이 미확정이므로, 표 간 동일 기준 비교·합산 여부는 추가 확인이 필요합니다.'
    refinement['metadata_constraints']=[{'type':'unknown_reporting_basis','source_ids':unknown,'message':notice,'origin':'source_metadata'}]
    for check in refinement.get('quality_checks',[]):
        if check.get('category')=='conflicting_basis':
            check.update(status='unresolved',reason=notice,source_ids=unknown,origin='source_metadata_guard')
    gaps=refinement.setdefault('remaining_gaps',[])
    if notice not in gaps:gaps.append(notice)
    guidance=refinement.setdefault('information_guidance',{})
    needs=guidance.setdefault('needed_contents',[])
    if not needs:guidance['explanation']=notice
    elif notice not in guidance.get('explanation',''):guidance['explanation']=guidance.get('explanation','')+' '+notice
    need='사용된 표의 연결·별도 작성 기준 및 표 간 비교 가능 여부'
    if need not in needs:needs.append(need)
    return output
