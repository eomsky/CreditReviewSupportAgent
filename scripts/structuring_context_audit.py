"""Expose unresolved table context per paragraph before review decisions."""
import copy,json


def augment(request,draft,evidence):
    request=copy.deepcopy(request)
    metadata={}
    for source in evidence:
        try:table=json.loads(source['text'])
        except (ValueError,TypeError):continue
        if table.get('table_id'):metadata[source['id']]=table
    focus=[]
    for paragraph in draft['paragraphs']:
        sources=[s['id'] for s in paragraph.get('sources',[]) if s['id'] in metadata]
        if len({metadata[s]['table_id'] for s in sources})>1 and any(metadata[s].get('basis') in (None,'unknown') for s in sources):
            focus.append({'paragraph_id':paragraph['id'],'source_ids':sources,'reporting_basis':'unconfirmed','required_review':'각 표의 관측 사실은 유지하되 표 간 인과·구성관계를 확정하는 구절이 있으면 실제 revisions에서 수정. unknown끼리 같다고 동일 기준으로 판단할 수 없음.'})
    if not focus:return request
    schema=request['structured_outputs']['json']
    audits={'type':'object','properties':{},'required':[],'additionalProperties':False}
    for item in focus:
        key=item['paragraph_id']
        audits['properties'][key]={'type':'object','properties':{'cross_table_claim':{'type':'string','maxLength':120},'decision':{'type':'string','enum':['revise_unsupported_link','independent_observations_only']},'reason':{'type':'string','maxLength':120}},'required':['cross_table_claim','decision','reason'],'additionalProperties':False}
        audits['required'].append(key)
    schema['properties']={'paragraph_context_audit':audits,**schema['properties']}
    schema['required']=['paragraph_context_audit',*schema['required']]
    schema['properties']['quality_checks']['properties']['conflicting_basis']['properties']['status']['enum']=['unresolved']
    payload=json.loads(request['messages'][-1]['content'])
    payload['mandatory_context_review']=focus
    payload['review_instruction']='paragraph_context_audit를 먼저 판단하고 revise_unsupported_link로 판정한 문단은 반드시 revisions로 실제 수정한다. 미확정 기준은 해소된 것으로 쓰지 않는다. 기존 심층 검토도 모두 수행한다.'
    request['messages'][-1]['content']=json.dumps(payload,ensure_ascii=False)
    return request
