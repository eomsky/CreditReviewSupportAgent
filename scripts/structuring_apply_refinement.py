"""Apply a finished structured-evidence review with the frozen validation path."""
import argparse,copy,json,sys,time,sqlite3,hashlib,re
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('folder',type=Path);p.add_argument('--normalize-change-audit',action='store_true');a=p.parse_args();folder=a.folder
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'outputs/frozen_candidates/C20.4-step2-r1/code/scripts'))
import review_refinement
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
state=read(folder/'trial/state.json');attempt=folder/'trial'/state['attempts'][-1]
response=read(attempt/'response.json')
if response['choices'][0]['finish_reason']!='stop':raise ValueError('Incomplete response')
parsed=json.loads(response['choices'][0]['message']['content'])
if 'information_guidance' not in parsed:
    gaps=parsed.get('remaining_gaps',[])
    parsed['information_guidance']={'explanation':review_refinement.explain_missing_information(gaps),'needed_contents':gaps}
def reject_duplicate_ids(node):
    if isinstance(node,dict):
        for key,value in node.items():
            if key in ('source_ids','affected_paragraph_ids') and isinstance(value,list) and len(value)!=len(set(value)):raise ValueError('Repeated evidence or paragraph IDs')
            reject_duplicate_ids(value)
    elif isinstance(node,list):
        for value in node:reject_duplicate_ids(value)
reject_duplicate_ids(parsed)
started=time.perf_counter();draft=read(folder/'draft.json');evidence=read(folder/'evidence.json')
if (folder/'supplemental-candidates.json').exists():
    decision=parsed.get('supplemental_normalization',{})
    if decision.get('decision')!='approve' or decision.get('issues')!=[]:raise ValueError('Unapproved supplementary facts')
    candidates=read(folder/'supplemental-candidates.json')
    db=sqlite3.connect(folder/'approved-supplement.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS approved_facts(id TEXT PRIMARY KEY,table_id TEXT,account TEXT,period TEXT,unit TEXT,value_decimal TEXT,source_id TEXT,cell TEXT,review_response_sha256 TEXT)')
    digest=hashlib.sha256((attempt/'response.json').read_bytes()).hexdigest()
    for fact in candidates:
        db.execute('INSERT OR REPLACE INTO approved_facts VALUES (?,?,?,?,?,?,?,?,?)',tuple(fact[k] for k in ('id','table_id','account','period','unit','value','source_id','cell'))+(digest,))
    db.commit();db.close()
    for source in evidence:
        table=json.loads(source['text'])
        pending=table.pop('pending_normalization_ids',[])
        if pending:table['approved_supplement_ids']=pending
        source['text']=json.dumps(table,ensure_ascii=False,separators=(',',':'))
if 'causal_basis' in parsed:
    by_source={s['id']:s.get('text','') for s in evidence}
    for decision in parsed['causal_basis'].values():
        if decision['decision']=='directly_supported':
            if not decision['quote'] or decision['quote'] not in by_source.get(decision['source_id'],''):raise ValueError('Causal evidence quote not found')
        elif decision['source_id'] is not None or decision['quote'] is not None:raise ValueError('Unsupported cause contains claimed evidence')
    (folder/'causal-basis.json').write_text(json.dumps(parsed['causal_basis'],ensure_ascii=False,indent=2),encoding='utf-8')
originals={p['id']:p for p in draft['paragraphs']}
patch_audit=[]
for revision in parsed.get('revisions',[]):
    if revision.get('replacements'):
        text=originals[revision['paragraph_id']]['text']
        for patch in revision['replacements']:
            if not patch['before'] or text.count(patch['before'])!=1:raise ValueError('Patch anchor must occur exactly once')
            text=text.replace(patch['before'],patch['after'],1)
        patch_audit.append({'paragraph_id':revision['paragraph_id'],'replacements':revision['replacements']})
        revision['text']=text
    if revision['action']=='keep':revision.update(text='',reason='기존 문단 유지',source_ids=[s['id'] for s in originals[revision['paragraph_id']].get('sources',[])])
if isinstance(parsed.get('quality_checks'),dict):parsed['quality_checks']=[{'category':k,**v} for k,v in parsed['quality_checks'].items()]
if patch_audit:(folder/'patch-audit.json').write_text(json.dumps(patch_audit,ensure_ascii=False,indent=2),encoding='utf-8')
result=review_refinement.apply_changes(copy.deepcopy(draft),parsed,evidence)
for basis in parsed.get('causal_basis',{}).values():
    for issue in basis.get('unsupported_claims',[]):
        old=originals[issue['paragraph_id']]['text']
        new=next(p['text'] for p in result['paragraphs'] if p['id']==issue['paragraph_id'])
        if old==new:raise ValueError('Declared unsupported claim paragraph unchanged')
        if issue.get('quote') and (issue['quote'] not in old or issue['quote'] in new):raise ValueError('Declared unsupported claim not resolved')
current_sources={s['id']:s for s in evidence}
for paragraph in result['paragraphs']:
    paragraph['sources']=[copy.deepcopy(current_sources[s['id']]) for s in paragraph.get('sources',[])]
changed={p['id'] for p in result['paragraphs'] if p['id'] in originals and p['text']!=originals[p['id']]['text']}
addition_anchors={v.get('after_id') for v in parsed.get('additions',[])}
if a.normalize_change_audit:
    from review_change_audit import normalize
    parsed['quality_checks'],change_audit=normalize(parsed.get('quality_checks',[]),changed|addition_anchors)
    (folder/'change-claim-audit.json').write_text(json.dumps(change_audit,ensure_ascii=False,indent=2),encoding='utf-8')
traceable=all(c.get('affected_paragraph_ids') and set(c['affected_paragraph_ids'])<=changed|addition_anchors for c in parsed.get('quality_checks',[]) if c.get('status')=='corrected' and 'affected_paragraph_ids' in c)
checks={'fixed_tables_preserved':result['tables']==draft['tables'],
        'citations_use_current_evidence':all(s==current_sources[s['id']] for p in result['paragraphs'] for s in p.get('sources',[])),
        'declared_corrections_traceable':traceable,
        'quality_categories_complete':{v['category'] for v in parsed.get('quality_checks',[])}=={'units_and_arithmetic','conflicting_basis','missing_vs_zero','causal_claims'},
        'original_paragraph_ids_preserved':set(p['id'] for p in draft['paragraphs'])<=set(p['id'] for p in result['paragraphs']),
        'all_citations_resolve':all(set(s['id'] for s in p.get('sources',[]))<={s['id'] for s in evidence} for p in result['paragraphs'])}
if not all(checks.values()):
    (folder/'invariant-failure.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    raise ValueError('Review invariant failure')
result['refinement']['quality_checks']=parsed.get('quality_checks',[])
from structuring_metadata_guard import apply as metadata_guard
result=metadata_guard(result,evidence)
# Keep source IDs in machine citations; render document names in reader guidance only.
request=read(folder/'refinement.request.json')
user_payload=json.loads(request['messages'][1]['content'])
label_by_doc={d['id']:d.get('name',d['id']) for d in user_payload.get('documents',[])}
labels={s['id']:label_by_doc[s['document_id']] for s in evidence if s.get('document_id') in label_by_doc}
def reader_text(value):
    if isinstance(value,str):
        for sid,label in labels.items():value=re.sub(r'(?<![A-Za-z0-9])'+re.escape(sid)+r'(?![A-Za-z0-9])',lambda m:label,value)
        return value
    if isinstance(value,list):return [reader_text(v) for v in value]
    if isinstance(value,dict):return {k:reader_text(v) for k,v in value.items()}
    return value
for key in ('remaining_gaps','information_guidance'):
    if key in result['refinement']:result['refinement'][key]=reader_text(result['refinement'][key])
(folder/'guidance-label-audit.json').write_text(json.dumps({'labels':labels,'machine_citations_unchanged':True},ensure_ascii=False,indent=2),encoding='utf-8')
(folder/'reviewed-artifact.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(folder/'reviewed-output.txt').write_text('\n\n'.join(p['heading']+'\n'+p['text'] for p in result['paragraphs']),encoding='utf-8')
audit={'checks':checks,'apply_seconds':time.perf_counter()-started,'quality_status':'requires_semantic_review','allow_step3':False,'end_to_end':False}
(folder/'apply-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(audit))
