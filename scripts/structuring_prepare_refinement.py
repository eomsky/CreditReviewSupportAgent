"""Reuse approved SQL evidence; preserve frozen refinement instructions and schema."""
import ast,copy,hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];accepted=root/'outputs/step_trials/C20.8s-cold-r1';out=root/'outputs/step_trials/C20.9s-step2-r3';out.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
gate=read(accepted/'step-result.json')
if not gate.get('allow_step2') or gate['quality_status']!='pass':raise ValueError('Step1 not accepted')
for name,digest in gate['artifact_sha256'].items():
    if hashlib.sha256((accepted/name).read_bytes()).hexdigest()!=digest:raise ValueError('Accepted artifact changed')
code=root/'outputs/frozen_candidates/C20.4-step2-r1/code/scripts';sys.path.insert(0,str(code))
import review_refinement as refinement
artifact=read(accepted/'materialized-artifact.json');evidence=artifact.pop('sources')
for i,p in enumerate(artifact['paragraphs']):
    p['id']='s-ga-'+str(i);source_ids=p.pop('source_ids');p['sources']=[copy.deepcopy(s) for s in evidence if s['id'] in source_ids]
# Keep the frozen review system construction, including every unconditional safeguard.
parsed=ast.parse((code/'review_refinement.py').read_text(encoding='utf-8'));fn=next(n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name=='refine')
prompt=read(accepted/'interpretation.request.json')['messages'][0]['content']
namespace={'prompt':prompt,'level':2,'with_reasoning':refinement.with_reasoning}
for node in fn.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('level_rules','system') for t in node.targets):
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<frozen-review-system>','exec'),namespace)
    elif isinstance(node,ast.AugAssign) and isinstance(node.target,ast.Name) and node.target.id=='system':
        exec(compile(ast.Module(body=[node],type_ignores=[]),'<frozen-review-system>','exec'),namespace)
system=namespace['system']+'\n수치 출처는 이미 원문 셀·기간·단위를 검수한 표별 SQL 결과다. 이번 호출에서 모든 본문 해석·인과·기간 비교와 표/본문 일치를 검토한다. 정규화 검수 완료가 본문 검토 완료를 뜻하지 않는다. 표 간 basis가 unknown이면 구성관계·인과를 확정하지 않는다.'
documents=read(root/'outputs/frozen_candidates/C20.4-step1-r1/run/financial_accounts.memory.json')['documents']
request={'model':read(accepted/'interpretation.request.json')['model'],'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps({'draft':refinement.draft_input(artifact),'documents':documents,'evidence_assessment':{'facts':[],'conflicts':[],'numeric_evidence':[],'arithmetic_checks':[]},'compressed_sources':evidence},ensure_ascii=False)}],'temperature':0.1,'max_tokens':8000,'chat_template_kwargs':{'enable_thinking':False},'structured_outputs':{'json':refinement.schema_for(artifact,evidence)}}
for name,value in [('refinement.request.json',request),('draft.json',artifact),('evidence.json',evidence),('provenance.json',{'parent':accepted.name,'scope':'ga review; approved SQL reused; no separate repeated preparation call','frozen_refinement_sha256':hashlib.sha256((code/'review_refinement.py').read_bytes()).hexdigest(),'all_unconditional_system_rules_preserved':True,'end_to_end':False})]:
    (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
print({'paragraphs':len(artifact['paragraphs']),'tables':len(artifact['tables']),'sources':len(evidence),'system_chars':len(system)})
