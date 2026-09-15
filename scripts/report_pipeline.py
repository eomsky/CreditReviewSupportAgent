"""Report drafting from reviewed opinions, followed by integration and A4 QA."""
import copy
import re
import report_table_review
import evidence_quality


def groups(outline):
    # Preserve user-defined order and titles, including custom outlines.
    n=len(outline)
    if n<=3:return [[row] for row in outline]
    first=n//3;second=(n-first)//2
    return [outline[:first],outline[first:first+second],outline[first+second:]]


def area_sources(area, evidence, fresh, manifest):
    """Keep area citations and new search results; integration retains all evidence."""
    ids={src['id'] for section in area['sections'] for p in section['paragraphs'] for src in p.get('sources',[])}
    ids.update(sid for section in area['sections'] for t in section.get('tables',[]) for sid in t.get('source_ids',[]))
    chosen={s['id']:s for s in evidence if s['id'] in ids}
    chosen.update({s['id']:s for s in fresh})
    documents={s['document_id'] for s in chosen.values()}
    for doc in manifest:
        if doc.get('required') and doc['id'] not in documents:
            source=next((s for s in evidence if s['document_id']==doc['id']),None)
            if source:chosen[source['id']]=source;documents.add(doc['id'])
    return list(chosen.values())


def pdf_check(api, report, folder, name):
    from report_export import export_report
    import pymupdf
    blocks=[]
    for section in report['sections']:
        blocks.append({'type':'heading','text':section['title']})
        tables=[t for t in section.get('tables',[]) if not t.get('needs_evidence') and t.get('template_id')!='evidence_status'];used=set()
        def emit(index):
            for i,t in enumerate(tables):
                if t.get('after_paragraph_index')==index:
                    blocks.append({'type':'table','caption':t.get('caption',''),'rows':[t['columns']]+t['rows'],'column_widths':t.get('column_widths')});used.add(i)
        emit(-1)
        for i,p in enumerate(section['paragraphs']):
            if p.get('heading') and p['heading']!=section['title']:blocks.append({'type':'heading','text':p['heading']})
            blocks.append({'type':'paragraph','text':p['text']});emit(i)
        for i,t in enumerate(tables):
            if i not in used:blocks.append({'type':'table','caption':t.get('caption',''),'rows':[t['columns']]+t['rows'],'column_widths':t.get('column_widths')})
    data=export_report({'format':'pdf','title':'심사보고서','sections':[{'title':'','blocks':blocks}]})
    (folder/(name+'.pdf')).write_bytes(data)
    with pymupdf.open(stream=data,filetype='pdf') as doc:
        pages=len(doc)
        # A nearly blank second page is not a substantive two-page report.
        last_lines=sum(len(b.get('lines',[])) for b in doc[-1].get_text('dict')['blocks'] if b['type']==0)
    chars=sum(len(p['text']) for s in report['sections'] for p in s['paragraphs'])
    check={'pages':pages,'last_page_lines':last_lines,'body_characters':chars,'target_met':pages>=2 and (pages>2 or last_lines>=8),'format':'A4 / 본문 10pt / 행간 16pt / 좌우 45pt','scope':'minimum_layout_only','quality_status':'unassessed'}
    api.app.dump(folder/(name+'.layout.json'),check)
    return check


def run(api,payload,folder,state,manifest,outline,generated,check_cancel,cancel_event):
    app=api.app;run=state['run'];start=run['completed_calls']
    prompt=payload.get('common_prompt','')+'\n\n'+'\n\n'.join(p['text'] for p in payload['generation_prompts']['report'])
    prompt+='\n'+(app.BASE/'prompts'/'report_reference_rules.txt').read_text(encoding='utf-8')
    prompt+='\n'+(app.BASE/'prompts'/'report_amount_units.txt').read_text(encoding='utf-8')
    # The supplied opinions have already passed refinement; their tables and
    # source excerpts are retained alongside fresh targeted retrieval.
    if not generated or any(not generated.get(k,{}).get('refinement') for k in app.VIEWS):
        raise api.DocumentError('심사보고서는 종합의견1·2의 검토 완료본이 필요합니다. 먼저 전체 의견 생성을 실행해 주세요.')
    app.dump(folder/'report.final_opinions.json',generated)
    prepared_excerpts=[];assessments=[];collected={};assembled={'case_id':state['id'],'draft':True,'sections':[]}
    for i,part in enumerate(groups(outline)):
        check_cancel()
        with app.lock:run.update(stage=f'심사보고서 {i+1}/{len(groups(outline))} · '+', '.join(x['title'] for x in part),phase='draft',completed_calls=start+i,report_parts_done=i,preview='',review_preview=[],item_percent=10)
        names=' '.join(x['title']+' '+x.get('description','') for x in part)
        mapping={'financial_accounts':['재무','자산','부채'],'profitability':['수익','손익'],'financial_stability':['안정','재무','위험'],'cashflow_repayment':['상환','현금','보전'],'customer_concentration':['영업','사업','산업'],'summary_2':['개요','신청','종합','경영','관계','조건']}
        keys=[key for key,terms in mapping.items() if any(term in names for term in terms)] or ['summary_2','financial_accounts']
        rows=api.STORE.select([x['title'].replace(' ','') for x in part]+api.TERMS[keys[0]],manifest,budget=12000,limit=12)
        seen={s['id'] for s in rows}
        for key in keys:
            for p in generated.get(key,{}).get('paragraphs',[]):
                for s in p.get('sources',[]):
                    if s['id'] not in seen:rows.append(copy.deepcopy(s));seen.add(s['id'])
        sub=folder/f'report-part-{i+1}';sub.mkdir()
        instructions=prompt+'\n이번 호출은 전체 보고서 중 '+names+'만 상세 작성한다. 다른 목차를 반복하지 않는다. prior_model_drafts는 검토가 끝난 의견이며 원문과 대조해 사용한다. 각 목차의 핵심 판단·수치와 원인·본 건 여신에 주는 의미를 2~4개 독립 문단으로 작성한다. 이미 표에 있는 숫자를 전부 반복하지 않는다. 전체 분량 중 이 영역이 충분한 분석 비중을 갖도록 하고 자료 없는 일반론은 추가하지 않는다.'
        instructions+='\n앞 영역에서 이미 사용한 표 유형(중복 선택 금지): '+str([t.get('template_id') for s in assembled['sections'] for t in s.get('tables',[])])
        relevant={key:generated[key] for key in keys if key in generated}
        planning_context={'full_outline':outline,'already_used_tables':[{'section':s['title'],'caption':t.get('caption'),'columns':t.get('columns')} for s in assembled['sections'] for t in s.get('tables',[])]}
        raw=api.complete(sub,'report',instructions,rows,relevant,report=True,manifest=manifest,outline=part,state=state,cancel_event=cancel_event,report_context=planning_context)
        assessments.append(raw.get('evidence_assessment',{}))
        check_cancel()
        included=app.json.loads((sub/'report.evidence.json').read_text(encoding='utf-8'))
        preparation=sub/'report.preparation.json'
        if preparation.exists():
            prepared_excerpts.extend(app.json.loads(preparation.read_text(encoding='utf-8')).get('source_excerpts',[]))
        collected.update({s['id']:s for s in included})
        # Subfolders all call the same generator; IDs must remain globally unique.
        for section in raw['sections']:
            for p in section['paragraphs']:p['id']=folder.name+'-'+p['id']
        assembled['sections'].extend(raw['sections'])
        with app.lock:
            state['report']=copy.deepcopy(assembled);state['revision']+=1;run.update(completed_calls=start+i+1,preview='');api.persist_case(state)
    evidence=list(collected.values())
    # Required-document review status is derived from actual final citations.
    cited={s['document_id'] for section in assembled['sections'] for p in section['paragraphs'] for s in p.get('sources',[])}
    assembled['required_document_reviews']=[{'document_id':d['id'],'document_name':d['name'],'status':'reflected' if d['id'] in cited else 'not_used','reason':'영역별 보고서의 원문 인용에 반영함' if d['id'] in cited else '선택된 원문 발췌에서 본문에 반영할 관련 근거를 확보하지 못함'} for d in manifest if d['required']]
    layout=pdf_check(api,assembled,folder,'report.draft')
    # Stage 1: review small areas with their evidence before cross-report review.
    for i,part in enumerate(groups(outline)):
        check_cancel()
        titles={x['title'] for x in part}
        area={'sections':[copy.deepcopy(s) for s in assembled['sections'] if s['title'] in titles]}
        search_terms=report_table_review.terms(area)
        fresh=report_table_review.retrieve(api.STORE,area,manifest) if search_terms else []
        collected.update({s['id']:s for s in fresh})
        evidence=list(collected.values())
        scoped=area_sources(area,evidence,fresh,manifest)
        ledger_ids={sid for row in assessments[i].get('numeric_evidence',[])+assessments[i].get('facts',[]) for sid in row['source_ids']}
        scoped=list({s['id']:s for s in scoped+[s for s in evidence if s['id'] in ledger_ids]}.values())
        area_memory={'draft':area,'evidence':scoped,'compressed_sources':api.review_refinement.compact_sources(scoped,area),'documents':manifest,'prompt':prompt,'prepared_context':assessments[i]}
        with app.lock:run.update(stage=f'심사보고서 · 상세 검토 {i+1}/{len(groups(outline))}',phase='refinement',completed_calls=start+len(groups(outline))+i,review_preview=[],item_percent=10)
        reviewed=api.review_refinement.refine(app,api.llm_stream,api.token_count,folder,f'report-area-{i+1}',area_memory,prompt+'\n1단계 영역별 상세 검토다. 문장 완결성, 접속어와 논리 방향, 표·본문 기준 일치, 빠진 원인·자금 유출입·상환시점·확인조건을 원문과 대조한다. 사실 재진술에 머문 문단은 원문의 새로운 정보를 찾아 심사상 의미를 보완한다. 수정 개수를 채우지 않되, 검토 수준이 최소여도 오류·끊긴 문장·핵심 근거 누락은 반드시 고친다. 추가 분석은 독립된 additions로 작성하며 표에서 근거 연결에 실패한 부분은 자료 부재와 구분하여 안내한다.',state,cancel_event)
        assessments[i]=reviewed.get('evidence_assessment',assessments[i])
        replacements={s['title']:s for s in reviewed['sections']}
        assembled['sections']=[replacements.get(s['title'],s) for s in assembled['sections']]
        assembled.setdefault('area_reviews',[]).append(reviewed.get('refinement',{}))
        assembled.setdefault('table_review',[]).extend(reviewed.get('table_review',[]))
        with app.lock:state['report']=copy.deepcopy(assembled);state['revision']+=1;run.update(completed_calls=start+len(groups(outline))+i+1,review_preview=[]);api.persist_case(state)
    memory={'draft':assembled,'evidence':evidence,'compressed_sources':api.review_refinement.compact_sources(evidence,assembled),'documents':manifest,'prompt':prompt,'prepared_context':evidence_quality.merge(assessments)}
    app.dump(folder/'report.memory.json',memory)
    integration=prompt+'\n2단계 최종 통합 검토: 영역별 상세 검토가 완료된 보고서다. 반복적인 전면 수정보다 목차 간 기준·수치·논리의 일관성, 중복 및 종합의견 연결을 확인한다. 전체 목차와 근거를 보존하면서 중복·모순을 최소 범위로 정리한다. 종합 심사의견에는 앞선 분석을 연결해 본 건 자금 용도·상환재원·중요 위험과 확인조건을 정리한다. 승인·거절을 임의로 결정하지 않는다. 심사보고서는 종합의견보다 깊은 분석을 제공해야 한다. 영역별 근거·원인·상환 영향·판단 조건을 연결하며, 최소 페이지 충족을 심사품질 통과로 취급하지 않는다. 글자·여백·반복 문장으로 분량을 늘리지 않는다.'
    if not layout['target_met']:integration+='\n현재 A4 출력의 내용량이 부족하다. 빈약한 목차의 원인·구성·시점·조건을 원자료에서 찾아 새로운 분석을 additions로 보완한다. 근거가 없으면 부족한 자료를 안내하고 억지로 분량을 채우지 않는다.'
    with app.lock:run.update(stage='심사보고서 · 통합 검토',phase='refinement',preview='',review_preview=[],item_percent=10)
    result=api.review_refinement.refine(app,api.llm_stream,api.token_count,folder,'report',memory,integration,state,cancel_event)
    check_cancel()
    result['layout_review']=pdf_check(api,result,folder,'report.final')
    if not result['layout_review']['target_met']:
        check_cancel()
        thin=sorted(result['sections'],key=lambda s:sum(len(p['text']) for p in s['paragraphs']))[:2]
        names=', '.join(s['title'] for s in thin)
        with app.lock:
            run['target_views'].append('report');run['total_calls']+=1
            run.update(completed_calls=start+len(groups(outline))*2+1,stage='심사보고서 · 부족 항목 보완',phase='refinement',review_preview=[],item_percent=10)
        memory['draft']=result
        result=api.review_refinement.refine(app,api.llm_stream,api.token_count,folder,'report-supplement',memory,integration+'\n선택 보완 대상: '+names+'. 다른 항목은 유지한다. 대상 항목에서 아직 다루지 않은 근거가 있는 논점만 추가한다. 근거가 없으면 추가하지 않고 information_guidance에 그 한계를 남긴다.',state,cancel_event)
        check_cancel()
        result['layout_review']=pdf_check(api,result,folder,'report.final')
    result['provenance']={'documents':manifest,'source':'검토 완료 의견 기반 3영역 작성 및 통합 검토','run_id':folder.name}
    result['layout_review']['note']='최소 분량 확인. 분석 깊이와 근거 품질은 별도 검증 대상임.' if result['layout_review']['target_met'] else '최소 분량 미달. 영역별 근거와 분석 충족도를 추가 검토해야 함.'
    with app.lock:
        state['report']=result;state['revision']+=1;run['report_layout']=result['layout_review'];run.update(completed_calls=run['total_calls'],preview='',review_preview=[],item_percent=100);api.persist_case(state)
