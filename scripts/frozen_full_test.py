"""Full frozen pipeline in a separate process and output tree; never persists live cases."""
import copy,hashlib,json,sys,time,threading,shutil
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
ID=sys.argv[1] if len(sys.argv)>1 else 'F3'
VERSION_ID=sys.argv[sys.argv.index('--version')+1] if '--version' in sys.argv else ID
VERSION_DESCRIPTION=sys.argv[sys.argv.index('--version-description')+1] if '--version-description' in sys.argv else ''
if VERSION_ID!=ID and not VERSION_DESCRIPTION:raise ValueError('A new revision requires --version-description')
RUNID=sys.argv[sys.argv.index('--run-id')+1] if '--run-id' in sys.argv else VERSION_ID
if not RUNID.startswith(VERSION_ID) or not all(c.isalnum() or c in '-.' for c in RUNID):raise ValueError('Invalid run id')
OUT=ROOT/'outputs/frozen_candidates'/RUNID
FROZEN=ROOT/'outputs/experiments/20260914/frozen'
CODE=OUT/'code'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix('.tmp')
    temp.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
    for _ in range(20):
        try:temp.replace(p);return
        except PermissionError:time.sleep(.05)
    raise OSError('save failed '+p.name)
OUT.mkdir(parents=True,exist_ok=False)
harness=OUT/'harness';harness.mkdir()
for helper in (ROOT/'scripts').glob('frozen_*.py'):shutil.copy2(helper,harness/helper.name)
if ID in ('C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):shutil.copy2(ROOT/'scripts/runtime_vector_store.py',harness/'runtime_vector_store.py')
sys.path.insert(0,str(harness))
for folder in ['scripts','prompts','frontend','docs']:shutil.copytree(FROZEN/folder,CODE/folder)
hashes={}
for name,expected in read(FROZEN/'manifest.json')['files'].items():
    name=name.replace('\\','/')
    if (CODE/name).is_file():
        actual=hashlib.sha256((CODE/name).read_bytes()).hexdigest()
        if actual!=expected:raise ValueError('Frozen copy mismatch '+name)
        hashes[name]=actual
sys.path.insert(0,str(CODE/'scripts'))
if ID in ('F4','F5','F6','F7','F8','C5','C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_parallel_patch import patch
    p=CODE/'scripts/business_report_test.py'
    original=p.read_text(encoding='utf-8');p.write_text(patch(original),encoding='utf-8')
    save(OUT/'code-changes.json',{'business_report_test.py':'Two independent opinion tasks concurrently; all drafting before reviews; summary after other drafts; frozen report pipeline unchanged.'})
if ID in ('F5','F6','F7','F8'):
    from frozen_report_parallel_patch import patch as report_patch
    from frozen_required_plan_patch import patch as plan_patch
    for name,transform in [('report_pipeline.py',report_patch),('prepared_context.py',plan_patch)]:
        p=CODE/'scripts'/name;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
    save(OUT/'code-changes.json',{'business_report_test.py':'Two independent opinion jobs concurrently.', 'report_pipeline.py':'Two independent detailed report reviews concurrently; final integration retained.', 'prepared_context.py':'Each requested report section has a required first table plan; same maximum total table count.'})
if ID in ('F6','F7','F8'):
    from frozen_report_draft_patch import patch as draft_patch
    from frozen_quote_span_patch import patch as quote_patch
    from frozen_table_address_patch import patch as address_patch
    from frozen_row_record_patch import patch as row_patch
    from frozen_repetition_patch import stream_patch,recovery_patch
    p=CODE/'scripts/report_pipeline.py';p.write_text(draft_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
    p=CODE/'scripts/prepared_context.py';p.write_text(quote_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
    p.write_text(row_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
    p=CODE/'scripts/semantic_table_review.py';p.write_text(address_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
    for name,transform in [('llm_stream.py',stream_patch),('llm_recovery.py',recovery_patch)]:
        p=CODE/'scripts'/name;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
    changes=read(OUT/'code-changes.json');changes['report_pipeline.py']+=' Report-area drafts also run two at a time; prior-area table visibility replaced by full-outline ownership guidance. Must assess duplicate-table risk.'
    changes['prepared_context.py']+=' Numeric quotes are exact source-line references, locally reconstructed before unchanged validation; all source text retained.'
    changes['prepared_context.py']+=' Table plans use row record identities plus first-column labels to avoid flattened cell lists.'
    changes['semantic_table_review.py']='Edit addresses include original row/column labels; decode to unchanged internal coordinates. Period/definition alignment guidance; no company-specific values.'
    changes['llm_stream.py']='Early detection of prolonged repeated output; abort only the current stream.'
    changes['llm_recovery.py']='Reuse bounded schema partitioning after a degenerate stream; no increased budget for meaningless output.'
    save(OUT/'code-changes.json',changes)
if ID in ('F7','F8'):
    from frozen_assessment_reference_patch import patch as reference_patch
    from frozen_review_order_patch import patch as review_order_patch
    from frozen_keep_encoding_patch import patch as keep_patch
    p=CODE/'scripts/review_refinement.py';p.write_text(keep_patch(review_order_patch(p.read_text(encoding='utf-8'))),encoding='utf-8')
    p=CODE/'scripts/prepared_context.py';p.write_text(reference_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
    changes=read(OUT/'code-changes.json');changes['prepared_context.py']+=' Incremental assessment can reuse exact prior numeric/table records by index; new/conflicting facts are still reassessed.'
    changes['review_refinement.py']='Four distinct quality dimensions precede paragraph decisions; original review/edit roles retained and category objects restored to existing audit arrays. Unchanged paragraph decisions omit repeated empty text/reason/citations; local restoration preserves original citations.'
    save(OUT/'code-changes.json',changes)
if ID=='F8':
    from frozen_audit_bound_patch import patch as audit_bound_patch
    p=CODE/'scripts/review_refinement.py';p.write_text(audit_bound_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
    changes=read(OUT/'code-changes.json');changes['review_refinement.py']+=' Internal quality-check reasons capped at 400 characters; report and paragraph limits unchanged.'
    save(OUT/'code-changes.json',changes)
if ID in ('C5','C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_required_plan_patch import patch as plan_patch
    from frozen_repetition_patch import stream_patch,recovery_patch
    from frozen_table_address_patch import patch as address_patch
    for name,transform in [('prepared_context.py',plan_patch),('llm_stream.py',stream_patch),('llm_recovery.py',recovery_patch),('semantic_table_review.py',address_patch)]:
        p=CODE/'scripts'/name;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
    save(OUT/'code-changes.json',{'business_report_test.py':'Two independent opinion workers; summary/report dependencies retained.', 'prepared_context.py':'Required table plan per report section.', 'semantic_table_review.py':'Original row and column labels accompany edit addresses.', 'llm_stream.py':'Abort degenerate repeated output; bounded existing recovery.'})
if ID in ('C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_budget_search_patch import patch as budget_patch
    from frozen_exact_template_patch import patch as exact_patch
    from frozen_continue_patch import patch as continue_patch
    p=CODE/'scripts/business_report_test.py';p.write_text(continue_patch(budget_patch(exact_patch(p.read_text(encoding='utf-8')))),encoding='utf-8')
    from frozen_quote_span_patch import patch as quote_patch
    from frozen_numeric_support_patch import patch as numeric_patch
    for name,transform in [('prepared_context.py',quote_patch),('evidence_quality.py',numeric_patch)]:
        p=CODE/'scripts'/name;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
    from frozen_assessment_reference_patch import patch as reference_patch
    p=CODE/'scripts/prepared_context.py';p.write_text(reference_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
    from frozen_report_parallel_patch import patch as report_review_patch
    from frozen_report_draft_patch import patch as report_draft_patch
    p=CODE/'scripts/report_pipeline.py';p.write_text(report_draft_patch(report_review_patch(p.read_text(encoding='utf-8'))),encoding='utf-8')
    from frozen_review_order_patch import patch as review_order_patch
    p=CODE/'scripts/review_refinement.py';p.write_text(review_order_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
    from frozen_nearest_header_patch import patch as header_patch
    p=CODE/'scripts/report_table_review.py';p.write_text(header_patch(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_exact_retrieval_patch import patch as exact_retrieval
    from frozen_json_transport_patch import patch as json_recovery
    from frozen_report_fallback_patch import patch as report_fallback
    from frozen_basis_context_patch import patch as basis_context
    from frozen_numeric_cells_patch import patch as numeric_cells
    from frozen_table_integrity_patch import semantic as table_integrity, refinement as body_integrity
    for name,transform in [('business_report_test.py',exact_retrieval),('llm_recovery.py',json_recovery),('report_pipeline.py',report_fallback),('semantic_table_review.py',basis_context),('semantic_table_review.py',numeric_cells),('semantic_table_review.py',table_integrity),('review_refinement.py',body_integrity)]:
        p=CODE/'scripts'/name;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_report_partial_patch import patch as partial_report
    from frozen_primary_scope_patch import patch as primary_scope
    from frozen_template_selection_patch import patch as template_selection
    from frozen_filled_retrieval_patch import patch as filled_retrieval, business as filled_business
    for name,transform in [('business_report_test.py',primary_scope),('business_report_test.py',template_selection),('business_report_test.py',filled_business),('report_table_review.py',filled_retrieval),('report_pipeline.py',partial_report)]:
        p=CODE/'scripts'/name;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_review_reuse_patch import patch as review_reuse
    p=CODE/'scripts/semantic_table_review.py';p.write_text(review_reuse(p.read_text(encoding='utf-8')),encoding='utf-8')
    from frozen_early_partition_patch import patch as early_partition
    p=CODE/'scripts/llm_recovery.py';p.write_text(early_partition(p.read_text(encoding='utf-8')),encoding='utf-8')
    from frozen_evidence_focus_patch import patch as evidence_focus
    p=CODE/'scripts/prepared_context.py';p.write_text(evidence_focus(p.read_text(encoding='utf-8')),encoding='utf-8')
    from frozen_table_arithmetic_patch import patch as table_arithmetic
    from frozen_keep_encoding_patch import patch as keep_encoding
    p=CODE/'scripts/review_refinement.py';p.write_text(table_arithmetic(keep_encoding(p.read_text(encoding='utf-8'))),encoding='utf-8')
    for name in ('business_report_test.py','report_pipeline.py'):
        p=CODE/'scripts'/name;p.write_text(p.read_text(encoding='utf-8').replace('max_workers=2','max_workers=4'),encoding='utf-8')
if ID in ('C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    # Keep an unattended active test from idling to sleep. This does not
    # override a user's sleep command or critical battery protection.
    import os,atexit
    if os.name=='nt':
        import ctypes
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        atexit.register(lambda:ctypes.windll.kernel32.SetThreadExecutionState(0x80000000))
    from frozen_earnings_slots_patch import patch as earnings_slots
    from frozen_stream_deadline_patch import patch as stream_deadline
    for name,transform in [('prepared_context.py',earnings_slots),('llm_stream.py',stream_deadline)]:
        p=CODE/'scripts'/name;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_report_table_reuse_patch import patch as report_table_reuse
    from frozen_causal_support_patch import patch as causal_support
    from frozen_report_memory_patch import patch as report_memory
    from frozen_integration_scope_patch import patch as integration_scope
    from frozen_numeric_transport_guard_patch import patch as transport_guard
    from frozen_transport_retry_patch import patch as transport_retry
    for name,transform in [('business_report_test.py',report_table_reuse),('business_report_test.py',report_memory),('review_refinement.py',causal_support),('report_pipeline.py',integration_scope),('semantic_table_review.py',transport_guard),('llm_stream.py',transport_retry)]:
        p=CODE/'scripts'/name;p.write_text(transform(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_summary_parallel_patch import patch as summary_parallel
    from frozen_input_boundary_patch import patch as input_boundary
    p=CODE/'scripts/business_report_test.py';p.write_text(summary_parallel(p.read_text(encoding='utf-8')),encoding='utf-8')
    p=CODE/'scripts/llm_recovery.py';p.write_text(input_boundary(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_joint_preparation_patch import patch as joint_preparation
    p=CODE/'scripts/business_report_test.py';p.write_text(joint_preparation(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C14','C15','C16','C17','C18','C19','C20'):
    from frozen_joint_bridge_patch import patch as joint_bridge
    p=CODE/'scripts/business_report_test.py';p.write_text(joint_bridge(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C15','C16','C17','C18','C19','C20'):
    from frozen_comparison_period_patch import patch as comparison_period
    p=CODE/'scripts/business_report_test.py';p.write_text(comparison_period(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C16','C17','C18','C19','C20'):
    from frozen_grammar_compat_patch import patch as grammar_compat
    p=CODE/'scripts/business_report_test.py';p.write_text(grammar_compat(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C17','C18','C19','C20'):
    from frozen_summary_after_analysis_patch import patch as summary_after_analysis
    p=CODE/'scripts/business_report_test.py';p.write_text(summary_after_analysis(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C18','C19','C20'):
    from frozen_table_basis_patch import patch as table_basis
    p=CODE/'scripts/business_report_test.py';p.write_text(table_basis(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID in ('C19','C20'):
    from frozen_financing_support_patch import patch as financing_support
    p=CODE/'scripts/business_report_test.py';p.write_text(financing_support(p.read_text(encoding='utf-8')),encoding='utf-8')
if ID=='C20':
    from frozen_balance_reasoning_patch import patch as balance_reasoning
    p=CODE/'scripts/business_report_test.py';p.write_text(balance_reasoning(p.read_text(encoding='utf-8')),encoding='utf-8')
if VERSION_ID in ('C20.1','C20.2','C20.3','C20.4','C20.14','C20.15'):
    from frozen_fewshot_patch import patch as fewshot
    p=CODE/'scripts/business_report_test.py';p.write_text(fewshot(p.read_text(encoding='utf-8')),encoding='utf-8')
if VERSION_ID in ('C20.2','C20.3','C20.4','C20.14','C20.15'):
    from frozen_earnings_paragraph_patch import patch as earnings_paragraph
    p=CODE/'scripts/business_report_test.py';p.write_text(earnings_paragraph(p.read_text(encoding='utf-8')),encoding='utf-8')
if VERSION_ID in ('C20.3','C20.4','C20.14','C20.15'):
    from frozen_earnings_source_order_patch import patch as earnings_source_order
    p=CODE/'scripts/business_report_test.py';p.write_text(earnings_source_order(p.read_text(encoding='utf-8')),encoding='utf-8')
if VERSION_ID in ('C20.4','C20.14','C20.15'):
    from frozen_required_topics_patch import patch as required_topics
    p=CODE/'scripts/business_report_test.py';p.write_text(required_topics(p.read_text(encoding='utf-8')),encoding='utf-8')
if VERSION_ID in ('C20.14','C20.15'):
    from frozen_joint_review_patch import patch as joint_review
    p=CODE/'scripts/review_refinement.py';p.write_text(joint_review(p.read_text(encoding='utf-8')),encoding='utf-8')
if VERSION_ID=='C20.15':
    from frozen_focused_review_patch import patch as focused_review
    p=CODE/'scripts/review_refinement.py';p.write_text(focused_review(p.read_text(encoding='utf-8')),encoding='utf-8')
if '--review-only' in sys.argv:
    p=CODE/'scripts/business_report_test.py'
    source=p.read_text(encoding='utf-8');assert source.count('        memories = {}')==1
    p.write_text(source.replace('        memories = {}',"        memories = copy.deepcopy(globals().get('_step_resume_memories',{}))"),encoding='utf-8')
import live_html_test as app
# Bootstrap the existing document store; generation uses an isolated cache/prompts below.
app.BASE=ROOT;app.CONFIG=ROOT/'workspace/llm_connection.json'
import business_report_test as api
app.BASE=CODE;app.ROOT=OUT
payload=read(FROZEN/'baseline_run/input.json')['payload']
payload=copy.deepcopy(payload);payload['case_id']='isolated-'+RUNID;payload['target_views']=app.VIEWS+['report']
if '--step1-only' in sys.argv:
    payload['target_views']=['financial_accounts']
    def step1_plan(request, generated):
        if request['target_views']!=['financial_accounts']:
            raise ValueError('Step 1 gate forbids another target')
        return ['financial_accounts'],[],False
    api.generation_plan=step1_plan
    save(OUT/'step-gate.json',{'step':1,'target_seconds':70,'quality_status':'unassessed',
         'allow_step2':False,'end_to_end':False,'scope':'financial_accounts drafting including retrieval and preparation'})
resume_folder=None
if '--review-only' in sys.argv:
    if '--step1-only' in sys.argv:raise ValueError('Conflicting step scopes')
    resume_folder=(ROOT/'outputs/frozen_candidates'/sys.argv[sys.argv.index('--resume-from')+1]).resolve()
    if resume_folder.parent!=(ROOT/'outputs/frozen_candidates').resolve():raise ValueError('Invalid resume location')
    gate=read(resume_folder/'step-gate.json')
    if gate.get('quality_status')!='pass' or gate.get('time_status') not in ('pass','provisional_pass') or not gate.get('allow_step2'):raise ValueError('Step 1 not accepted')
    for name,digest in gate['artifact_sha256'].items():
        if hashlib.sha256((resume_folder/name).read_bytes()).hexdigest()!=digest:raise ValueError('Accepted artifact changed')
    payload['target_views']=['financial_accounts']
    def review_plan(request,generated):
        if request['target_views']!=['financial_accounts'] or 'financial_accounts' not in generated:raise ValueError('Invalid review target')
        return [],['financial_accounts'],False
    api.generation_plan=review_plan
    api._step_resume_memories={'financial_accounts':read(resume_folder/'run/financial_accounts.memory.json')}
    save(OUT/'step-gate.json',{'step':2,'target_seconds':50,'quality_status':'unassessed','allow_step3':False,'end_to_end':False,'resumed_from':resume_folder.name,'input_sha256':gate['artifact_sha256']})
preprocessing_started=time.monotonic()
if ID in ('C2','C3'):
    sys.path.insert(0,str(ROOT/'src'))
    from frozen_structured_sources import StructuredStore
    artifacts={}
    for path in (ROOT/'outputs/frozen_candidates').glob('structured-*-probe/timings.json'):
        artifacts[read(path)['pdf_sha256']]=path.parent
    api.STORE=StructuredStore(api.STORE,artifacts,mode='dense' if ID=='C3' else 'keyword',vector_path=ROOT/'outputs/frozen_candidates/controlled-vector-index')
    save(OUT/'input-adapter.json',{'mode':'dense_keyword' if ID=='C3' else 'structural_keyword','artifact_hashes':list(artifacts),'preprocessing_seconds':time.monotonic()-preprocessing_started,'generation_rules':'frozen unchanged'})
if ID=='C4':
    from frozen_original_vector_sources import OriginalVectorStore
    api.STORE=OriginalVectorStore(api.STORE,payload['documents'],FROZEN,ROOT/'outputs/frozen_candidates/frozen-vector-index')
    save(OUT/'input-adapter.json',{'mode':'frozen_dense_keyword','frozen_source_hashes':api.STORE.source_hashes,'vector_index':api.STORE.vector.info,'preprocessing_seconds':time.monotonic()-preprocessing_started,'generation_rules':'frozen unchanged','tuned_extractor':False})
if ID in ('C5','C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    from frozen_page_vector_sources import PageVectorStore
    if ID in ('C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
        from runtime_vector_store import RuntimePageStore
        api.STORE=RuntimePageStore(api.STORE,ROOT/'outputs/frozen_candidates/runtime-equivalence-index')
        api.STORE.source_hashes={}
    else:
        api.STORE=PageVectorStore(api.STORE,payload['documents'],FROZEN,ROOT/'outputs/frozen_candidates/page-vector-index')
    save(OUT/'input-adapter.json',{'mode':'frozen_page_rrf','frozen_source_hashes':api.STORE.source_hashes,'vector_index':api.STORE.vector.info,'preprocessing_seconds':time.monotonic()-preprocessing_started,'whitespace':'PDF padding collapsed, non-whitespace characters preserved','tuned_extractor':False})
if ID in ('C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):app.review_source_store=api.STORE
state={'id':payload['case_id'],'name':payload.get('company_name','시험'),'revision':0,'views':{},'report':{'sections':[]},'run':{'id':'run','status':'running','stage':'시작','completed_calls':0,'review_level':payload.get('review_level',0)}}
if resume_folder:state['views']={'financial_accounts':copy.deepcopy(api._step_resume_memories['financial_accounts']['draft'])}
api.CASES={state['id']:state}
api.persist_case=lambda s:save(OUT/'state.json',s)
start=preprocessing_started if ID in ('C1','C2','C3','C4','C5','C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20') else time.monotonic();calls=[];call_lock=threading.Lock()
transport=api.llm_stream.complete
def normalized(messages):
    if ID in ('C1','C2','C3','C4','C5'):
        return copy.deepcopy(messages)  # Controlled comparison: no prompt optimization.
    result=copy.deepcopy(messages)
    for m in result:
        if ID in ('F7','F8') and m.get('role')=='user' and isinstance(m.get('content'),str):
            try:
                parsed=json.loads(m['content'])
                if isinstance(parsed,(dict,list)):m['content']=json.dumps(parsed,ensure_ascii=False,separators=(',',':'))
            except (ValueError,TypeError):pass
        if m.get('role')!='system' or not isinstance(m.get('content'),str):continue
        seen=set();kept=[]
        for line in reversed(m['content'].splitlines()):
            if len(line)>40 and line in seen:continue
            seen.add(line);kept.append(line)
        m['content']='\n'.join(reversed(kept))
        if ID in ('C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
            from frozen_basis_context_patch import BASIS_RULES
            m['content']+='\n'+BASIS_RULES
        if ID in ('F5','F6','F7','F8','C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
            from frozen_prompt_scope import scope
            tag=getattr(getattr(api,'_experiment_local',None),'tag','')
            key=tag.split(':',1)[1] if tag.startswith(('draft:','review:')) else ''
            m['content']=scope(m['content'],key)
    return result
original_count=api.token_count
token_measurements=[]
def instrumented_count(messages):
    began=time.monotonic()
    record={}
    try:
        result=original_count(normalized(messages))
        if ID in ('C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
            tag=getattr(getattr(api,'_experiment_local',None),'tag','')
            result=(result[0],min(result[1],65536 if tag=='report-integration' else 32768))
        record.update(count=result[0],maximum=result[1],status='completed')
        return result
    except Exception as error:
        record.update(status='failed',error_type=type(error).__name__,http_status=getattr(error,'code',None))
        raise
    finally:
        if ID in ('C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
            with call_lock:
                token_measurements.append({**record,'stage':getattr(getattr(api,'_experiment_local',None),'tag',''),'elapsed_seconds':round(time.monotonic()-began,4)})
                save(OUT/'token-count-timings.json',token_measurements)
api.token_count=instrumented_count
def measured(config,request,on_delta,**kwargs):
    req=copy.deepcopy(request);req['messages']=normalized(req['messages'])
    if ID in ('C5','C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20') and 'json' in req.get('structured_outputs',{}):
        from frozen_review_reason_bound import bound_schema
        req['structured_outputs']['json']=bound_schema(req['structured_outputs']['json'])
    with call_lock:
        n=len(calls)+1;record={'number':n,'stage':getattr(getattr(api,'_experiment_local',None),'tag',state['run'].get('stage')),'status':'running','started_seconds':round(time.monotonic()-start,2)};calls.append(record)
    from frozen_timing_report import classify
    record['operation']=classify(req)
    record['removed_user_characters']=sum(len(m.get('content','')) for m in request['messages'] if m.get('role')=='user')-sum(len(m.get('content','')) for m in req['messages'] if m.get('role')=='user')
    record['removed_system_characters']=sum(len(m.get('content','')) for m in request['messages'] if m.get('role')=='system')-sum(len(m.get('content','')) for m in req['messages'] if m.get('role')=='system')
    save(OUT/'calls'/f'{n:03}.request.json',req)
    began=time.monotonic()
    try:
        response=transport(config,req,on_delta,**kwargs)
        save(OUT/'calls'/f'{n:03}.response.json',response)
        record.update(status='truncated' if response['choices'][0].get('finish_reason')=='length' else 'completed',usage=response.get('usage'),finish_reason=response['choices'][0].get('finish_reason'))
        return response
    except Exception as e:
        record.update(status='failed',error=type(e).__name__)
        if getattr(e,'partial_text',None):(OUT/'calls'/f'{n:03}.interrupted.txt').write_text(e.partial_text,encoding='utf-8')
        raise
    finally:
        record['elapsed_seconds']=round(time.monotonic()-began,2)
        with call_lock:save(OUT/'calls.json',calls)
api.llm_stream.complete=measured
changes=['Exact repeated long system-instruction lines removed; all generation/preparation/table/body/report/integration review stages preserved. No v1-v6 generation code.']
if ID in ('C1','C2','C3','C4'):changes=['Frozen prompts and generation/review rules unchanged; only the explicitly described input/retrieval adapter differs.']
if ID in ('F4','F5','F6','F7','F8'):changes.append('Independent opinion drafting and review concurrency limited to two; summary/report dependency barriers preserved.')
if ID in ('F5','F6','F7','F8'):changes.append('Independent detailed report review concurrency limited to two; required first table plan per report section; final integration retained.')
if ID in ('F5','F6','F7','F8'):changes.append('Individual opinion requests retain shared/target instructions while excluding other sections in the recognized frozen catalogue. Report instructions and all source evidence remain intact.')
if ID in ('F6','F7','F8'):changes.append('Report drafts overlap at two workers; preceding-area table context unavailable until assembly. Full-outline ownership and final integration retained; quality risk requires comparison.')
if ID in ('F6','F7','F8'):changes.append('Numeric quote text encoded as source line spans; exact local reconstruction before the original numeric-source validation. No source or review omitted.')
if ID in ('F6','F7','F8'):changes.append('Table edit coordinates include original metric/period labels and are reversibly decoded to existing coordinates; source alignment guidance strengthened.')
if ID in ('F6','F7','F8'):changes.append('Table planning identifies the record represented by each row before its first-column value; preserves record identity in generation guidance.')
if ID in ('F6','F7','F8'):changes.append('Degenerate repeated output is stopped early and retried with existing bounded schema partitioning; all requested fields retained.')
if ID in ('F7','F8'):changes.append('Prior assessed numeric/table records can be referenced instead of re-generated; exact local copy followed by existing source validation. Four distinct quality dimensions precede edit decisions. Keep decisions use two fields and restore original citations locally; all paragraph decisions remain required. JSON structural whitespace compacted losslessly while preserving every source string, field and numeric value.')
if ID=='F8':changes.append('Internal audit reason maxLength 400; body/edit text remains unconstrained by this adapter. Must validate server enforcement and quality.')
if ID in ('C5','C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes=['Frozen extraction with page-level dense/keyword RRF, title matching and adjacent numeric continuation; PDF padding compacted without dropping non-whitespace content. Two independent opinion workers. Required report table plans. Labelled table edit coordinates. Internal reason/calculation fields bounded to 320 characters; body text unchanged. Existing repetition recovery. Full generation and all review stages retained.']
if ID in ('C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Binary search over the existing evidence removal order; protected sources and required documents retained. Token counter timings recorded. Verify tokenizer boundary equivalence. Complete source-authored XLSX fixed tables with exact title/unit/rows/columns/periods are copied locally, with source priority and equal-priority conflict rejection. Semantic review retained; unmatched tables remain model-generated. Numeric quotations restored from exact selected source lines; accounting parentheses recognized as negative lexical values. Report-area drafts/reviews overlap at two workers with ownership guidance; final integration retained, duplicate-table/dependency risk must be assessed.')
if ID in ('C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Additional assessment reuses previous numeric/table records by index with exact restoration. Four bounded review dimensions precede paragraph decisions; unchanged original body/edit fields retained.')
if ID in ('C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Only recognized multi-section instruction catalogues are scoped to the current opinion, retaining shared/report instructions; duplicate identical long system lines removed. User evidence strings and body content untouched.')
if ID in ('C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Source-count limit restored with a required-document full-bundle exception; closest preceding header only and PDF padding compaction retained on get(). Per-item failures recorded without suppressing independent opinion/report attempts; partial results remain failed, never marked complete.')
if ID in ('C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Complete exact source-authored fixed tables explicitly reserved across uploaded XLSX before drafting; vector retrieval remains for all other evidence. Invalid JSON string control characters escaped losslessly; other JSON errors get one retry. Missing prior opinions do not block source-grounded report attempt; partial failure status retained.')
if ID in ('C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Source-authored exact tables skip redundant numerical regeneration; semantic basis/causality review remains in the body review with original tables and sources. Unbound monetary fixed tables select labelled original numeric tokens, verified units/period headers, then Decimal materialization; no guessed monetary values. Source-authored/selected values preserved during later reviews; conflicting proposals recorded. Identical customer display tuples deduplicated independently per period. PDF table scope restricted only on an exact unique title/header match, otherwise original evidence retained.')
if ID in ('C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Fully source-authored financial views use the source document scope for numeric comparability; cross-document analysis retained in summary/report. Filled unbound financial tables trigger evidence retrieval. Layout examples retrieved from full catalogue with compact full index; custom layouts allowed. Follow-up retrieval uses same vector store. Concurrency unchanged at two pending runtime reconnection.')
if ID in ('C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Supersedes C8 concurrency note: four independent workers; requires server max-num-seqs=4 before launch. Runtime incremental upload adapter, same PDF extraction and verified retrieval equivalence; embedding build charged on first use. No candidate fixture loader for upload retrieval. Numeric-token labels only on requests using numeric references. Conflicting exact template values at any priority fall back to semantic resolution; priority never chooses accounting truth. Keep paragraph decisions send ID/action only with exact original paragraph/citation preservation; every paragraph decision and all quality checks remain required. Source-authored table period-pair arithmetic is computed with Decimal and supplied to review to prevent erroneous mental recalculation; accounting comparability is still reviewed. Evidence selection prioritizes causal/earnings-bridge records rather than transcribing the first 16 table cells; financial source retrieval reserves the earnings bridge excerpt. Early schema partition also covers 4500/5000-token requests when their actual output window is below 4096, avoiding predictably truncated first attempts. Table review locations exclude already-reviewed tables of the current quality version. Unreferenced numeric edits are rejected and original values retained with explicit verification_gaps rather than aborting the full report area; these gaps are not quality approval.')
if ID in ('C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Initial financial evidence uses explicit earnings-role slots, flattened to the unchanged source validation and arithmetic ledger; missing roles may remain empty. SSE watchdog bounds actual-output stalls and overall request duration, never accepts partial responses. C9 was infrastructure interrupted and provides no complete quality/performance result.')
if ID in ('C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Only uniquely source-proven numeric period coordinates can be realigned; fixed template period headers remain fixed. Report plans exactly matching reviewed source-authored table projections reuse cells; body semantic review retained. Initial report planning may reference prior source-verified numeric records without repeating their serialization; all selected original sources are still presented and records are revalidated. Causal review separately assesses asset-quality details, collateral realization evidence and earnings levels versus changes. Final integration retains current claims and all their original citations, ledger support and required-document coverage; unused retrieval candidates remain in detailed review artifacts. Server native context 64K permitted only for serial report integration; normal concurrent stages remain capped at 32K. Connection resets before or during SSE use the existing one-retry bound; interrupted text is never accepted. Actual full quality and timing must still pass.')
if ID in ('C12','C13','C14','C15','C16','C17','C18','C19','C20'):changes.append('Source-grounded summary_2 starts among the first four draft jobs with no mutable prior-model drafts; all six opinions still complete drafting before review. C8/C10 already excluded prior drafts under their input budget, so the prior sequential wait did not contribute to their actual summary prompts. A pre-inference boundary reserves the requested output and 512 safety tokens, selects complete source excerpts in the original relevance order, preserves cited/assessed support and required-document coverage, and narrows allowed source aliases. No arbitrary text-prefix truncation. Indispensable context larger than the model window remains an explicit limitation. Must validate full quality and scheduling.')
save(OUT/'provenance.json',{'baseline':str(FROZEN),'hashes':hashes,'changes':changes, 'input_scope':'Previously extracted documents; fresh isolated preparation cache','quality_status':'pending','rollback':'Production not modified; discard isolated candidate.'})
web=ROOT/'outputs/business_report_test/experiment-monitor-state.json'
monitor=read(web)
session=read(ROOT/'outputs/frozen_candidates/session-2h.json')
monitor.update(started_at=session['started_at'],end_at=session['end_at'])
version={'id':RUNID,'description':'프리징본 전체 경로 · 동일 지침 중복 제거'+(' · 독립 의견 2개 동시 처리' if ID in ('F4','F5','F6','F7','F8') else '')+(' · 항목별 지침 선택 · 보고서 영역 검토 병렬화 · 필수 표 계획' if ID in ('F5','F6','F7','F8') else '') + (' · 보고서 생성 병렬화' if ID in ('F6','F7','F8') else ''),'status':'running','started_at':datetime.now().astimezone().isoformat(),'steps':[],'text':''}
if ID in ('F7','F8'):version['description']+=' · 기존 기록 참조 · 품질 점검 선행 · 유지 판정 축약'
if ID=='F8':version['description']+=' · 내부 점검 사유 반복 제한'
monitor['versions'].append(version)
if '--step1-only' in sys.argv:version['step_scope']=1
if resume_folder:
    version['step_scope']=2
    version['carried_steps']=[{'name':'0 draft:financial_accounts · 보존 초안','status':'completed','elapsed_seconds':gate['elapsed_seconds'],'quality_status':'pass','pass_version':resume_folder.name}]
if ID in ('C5','C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):
    version['description']='벡터·키워드 페이지 검색 · 이어지는 표 보강 · 내부 사유 길이 제한 · 의견 2개 병렬'
    if ID in ('C6','C7','C8','C9','C10','C11','C12','C13','C14','C15','C16','C17','C18','C19','C20'):version['description']='벡터 페이지 검색 · 원문 고정표 복사 · 원문 참조 재사용 · 입력조정 조회 감소 · 보고서 병렬'
    save(OUT/'candidate-changes.json',{'controlled_comparison':False,'description':version['description'],'changes':changes})
if ID in ('C1','C2','C3','C4'):
    version['description']={'C1':'대조군: 프리징본 그대로','C2':'튜닝 추출기 + 기존 키워드 검색','C3':'튜닝 추출기 + 로컬 임베딩/Qdrant + 키워드 검색','C4':'프리징 추출 방식 + 로컬 임베딩/Qdrant + 키워드 검색'}[ID]
    save(OUT/'candidate-changes.json',{'controlled_comparison':True,'description':version['description'],'prompt_optimization':False,'other_F_changes':False})
if VERSION_DESCRIPTION:
    version['description']=VERSION_DESCRIPTION
    version['version_id']=VERSION_ID
    save(OUT/'version-info.json',{'version':VERSION_ID,'base_profile':ID,'description':VERSION_DESCRIPTION})
done=threading.Event()
def readable():
    out=[]
    for s in list(state.get('views',{}).values())+state.get('report',{}).get('sections',[]):
        out.append(s.get('title',''))
        out.extend(p.get('text','') for p in s.get('paragraphs',[]))
        for t in s.get('tables',[]):
            out.append(t.get('caption',''));out.append(' | '.join(map(str,t.get('columns',[]))))
            out.extend(' | '.join('—' if v is None else str(v) for v in row) for row in t.get('rows',[]))
    return '\n\n'.join(out)
def publish():
    while True:
        monitor['stage']=RUNID+' · '+state['run'].get('stage','');monitor['updated_at']=datetime.now().astimezone().isoformat()
        version.update(status=state['run']['status'],elapsed_seconds=round(time.monotonic()-start,2),text=readable())
        version['steps']=[{'name':str(c['number'])+' '+str(c['stage'])+' · '+c.get('operation',''),'status':c['status'],'elapsed_seconds':c.get('elapsed_seconds',round(time.monotonic()-start-c['started_seconds'],2))} for c in calls]
        try:save(web,monitor)
        except OSError:pass
        if done.wait(2):break
t=threading.Thread(target=publish,daemon=True);t.start()
try:api.worker(payload,'run')
finally:
    done.set();t.join()
    version.update(status=state['run']['status'],elapsed_seconds=round(time.monotonic()-start,2),text=readable())
    version['steps']=[{'name':str(c['number'])+' '+str(c['stage'])+' · '+c.get('operation',''),'status':c['status'],'elapsed_seconds':c.get('elapsed_seconds',0)} for c in calls]
    if state['run'].get('error'):version['error']=state['run']['error']
    monitor['stage']=RUNID+' · '+state['run']['status']+' · 품질 비교 대기';save(web,monitor)
    save(OUT/'results.json',version);save(OUT/'state.json',state)
    (OUT/'full-output.txt').write_text(version['text'],encoding='utf-8')
    print(json.dumps(state['run'],ensure_ascii=False),flush=True)
    if hasattr(api.STORE,'vector'):api.STORE.vector.client.close()
