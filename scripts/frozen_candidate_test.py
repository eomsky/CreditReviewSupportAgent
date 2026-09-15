"""F1: frozen generation requests + shared original table evidence. Isolated partial test."""
import copy, hashlib, json, sys, time, re
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'outputs/experiments/20260914/frozen'
BASE=FROZEN/'baseline_run'
ID=sys.argv[1] if len(sys.argv)>1 else 'F1'
OUT=ROOT/'outputs/frozen_candidates'/ID
sys.path.insert(0,str(FROZEN/'scripts'))
import llm_stream, fixed_review_tables, summary2_structure, prepared_context

def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def text(r):
    out=[r.get('title','')]
    for p in r.get('paragraphs',[]):out.extend([p.get('heading',''),p['text']])
    for t in r.get('tables',[]):
        out.extend([t.get('caption',''),' | '.join(map(str,t['columns']))])
        out.extend(' | '.join('—' if v is None else str(v) for v in row) for row in t['rows'])
    return '\n\n'.join(out)

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    manifest=read(FROZEN/'manifest.json')['files']
    checked={}
    for name,expected in manifest.items():
        name=name.replace('\\','/')
        if name.startswith(('scripts/','prompts/')):
            actual=digest(FROZEN/name)
            if actual!=expected:raise ValueError('동결 파일 해시 불일치: '+name)
            checked[name]=actual
    if not checked:raise ValueError('동결 코드 검증 대상 없음')
    sources={}
    # Reuse the native, coordinate-preserving excerpts already selected for fixed tables.
    # No company, date, account value, or source identifier is hardcoded.
    for key in fixed_review_tables.TEMPLATES:
        p=BASE/(key+'.evidence.json')
        if p.exists():
            for s in read(p):
                if s.get('table_coverage'):sources[s['id']]=s
    if ID!='F1':
        candidates=list(sources.values());sources={}
        for templates in fixed_review_tables.TEMPLATES.values():
            for template in templates:
                labels=template.get('labels',[])
                if not labels or template.get('customer'):continue
                ranked=[]
                for s in candidates:
                    native_labels=re.findall(r'(?:^|\n)A\d+=([^|\n]+)',s['text'])
                    score=sum(label in [x.strip() for x in native_labels] for label in labels)
                    if score>=max(2,len(labels)//2):ranked.append((score,s))
                if ranked:
                    s=max(ranked,key=lambda x:x[0])[1];sources[s['id']]=s
    if not sources:raise ValueError('고정 표 공통 근거 없음')
    save(OUT/'shared-original-evidence.json',list(sources.values()))
    save(OUT/'provenance.json',{'baseline':str(FROZEN),'verified_hashes':checked,
      'scope':'financial_accounts and summary_2 generation only; not end-to-end',
      'change':'Shared native table evidence; F2 additionally removes exact repeated instructions and other-section detailed prompts. Target-section instructions, common reasoning and schema retained.',
      'rollback':'Production untouched. Reject F1 and use immutable frozen baseline.',
      'reference_only':['v1','v2','v3','v4','v5','v6']})
    config=read(ROOT/'workspace/llm_connection.json')
    web=ROOT/'outputs/business_report_test/experiment-monitor-state.json'
    state=read(web)
    now=datetime.now().astimezone().isoformat()
    state.update(started_at=now,stopped_at=None,status='running',stage='F1 · 프리징본 기반 부분 시험',deadline_disabled=True)
    version={'id':ID,'description':'프리징본 + 공통 표 원문 · 가/종2 부분 시험','status':'running','started_at':now,'steps':[],'text':''}
    state['versions'].append(version)
    def publish():
        state['updated_at']=datetime.now().astimezone().isoformat()
        version['text']='\n\n'.join('【'+s['name']+'】\n'+s.get('text','') for s in version['steps'])
        try:save(web,state)
        except OSError:pass
    start=time.monotonic()
    for key in ['financial_accounts','summary_2']:
        step={'name':key,'status':'running','text':''};version['steps'].append(step);publish()
        began=time.monotonic()
        try:
            req=read(BASE/(key+'.request.json'));original=copy.deepcopy(req)
            if ID in ('F1c','F2'):
                lines=req['messages'][0]['content'].splitlines();seen=set();kept=[];removed=[]
                for line in reversed(lines):
                    if len(line)>40 and line in seen:removed.append(line);continue
                    seen.add(line);kept.append(line)
                req['messages'][0]['content']='\n'.join(reversed(kept))
                save(OUT/(key+'.exact-duplicate-instructions.json'),removed)
            if ID=='F2':
                system=req['messages'][0]['content']
                start_marker='\n가. 재무제표 주요계정(현황 및 향후전망)\n' if key=='summary_2' else '\n나. 수익성(현황 및 향후전망)\n'
                end_marker='\n종합의견2 — 조사자 종합의견\n' if key=='summary_2' else '\n심사보고서 작성 지침\n'
                a=system.index(start_marker);b=system.index(end_marker,a)
                save(OUT/(key+'.other-section-instructions.json'),{'removed':system[a:b],'reason':'Requested section and shared reasoning instructions retained; other sections are generated separately.'})
                req['messages'][0]['content']=system[:a]+system[b:]
            body=json.loads(req['messages'][1]['content'])
            native=read(BASE/(key+'.evidence.json'))
            aliases={s['id']:n for s,n in zip(body['sources'],native)}
            original_ids={s['id'] for s in native}
            for sid,s in sources.items():
                if sid in original_ids:continue
                alias='S'+str(len(aliases)+1);aliases[alias]=s
                body['sources'].append({'id':alias,'document_id':s['document_id'],'page':s.get('page'),'text':s['text']})
            body['shared_original_table_refs']=[a for a,s in aliases.items() if s['id'] in sources]
            req['messages'][0]['content']+='\n共通原文: shared_original_table_refs는 다른 영역에서도 재사용하는 원문이다. 기존 본문 깊이와 심사 논리는 유지한다. 동일 계정·기간·기준의 수치와 표 단위를 서로 대조한다. 배와 % 및 영업활동후CF와 실제 영업활동 현금흐름은 다른 개념이므로 임의로 대체하지 않는다. 금액을 억원 등으로 바꿀 때 환산을 확인한다. 요약과 상세의 단위가 충돌하면 분자·분모 또는 원문 정의를 확인하고, 해소되지 않으면 위험이 낮다거나 상환능력이 충분하다고 단정하지 않는다. 앞선 초안보다 원문을 우선하며 미확인 기재 전 공통 원문도 확인한다.'
            req['messages'][1]['content']=json.dumps(body,ensure_ascii=False)
            def refs(node):
                if isinstance(node,dict):
                    if 'source_ids' in node.get('properties',{}):node['properties']['source_ids']['items']['enum']=list(aliases)
                    for x in node.values():refs(x)
                elif isinstance(node,list):
                    for x in node:refs(x)
            refs(req['structured_outputs']['json'])
            endpoint=config['base_url'].rstrip('/').removesuffix('/v1')
            tok=Request(endpoint+'/tokenize',data=json.dumps({'model':config['model'],'messages':req['messages'],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}).encode(),headers={'Authorization':'Bearer '+config['api_key'],'Content-Type':'application/json'})
            with urlopen(tok,timeout=60) as r:count=json.load(r)
            save(OUT/(key+'.token-budget.json'),count)
            if count['count']+req['max_tokens']+256>(count.get('max_model_len') or 32768):raise ValueError('원문·본문 예산 보존 조건에서 문맥 초과: 분리 설계 필요')
            save(OUT/(key+'.request.json'),req);save(OUT/(key+'.aliases.json'),aliases)
            step['input_tokens']=count['count'];last=[0]
            def progress(delta,full):
                step['text']=full
                if time.monotonic()-last[0]>2:last[0]=time.monotonic();publish()
            response=llm_stream.complete(config,req,progress,timeout=600)
            save(OUT/(key+'.response.json'),response)
            if response['choices'][0]['finish_reason']!='stop':raise ValueError('출력 미완결')
            r=json.loads(response['choices'][0]['message']['content'])
            save(OUT/(key+'.raw-result.json'),r)
            if key in fixed_review_tables.TEMPLATES:
                r['paragraphs'].extend(r.pop('analysis_paragraphs'));fixed_review_tables.apply(r,key)
            else:
                summary2_structure.flatten(r)
                prepared_context.apply(r,body['prepared_context'],aliases)
            save(OUT/(key+'.result.json'),r)
            step.update(status='completed',text=text(r),usage=response.get('usage'))
        except Exception as error:
            step.update(status='failed',error=type(error).__name__+': '+str(error))
        step['elapsed_seconds']=round(time.monotonic()-began,2);publish()
    version.update(status='partial_test_completed' if all(s['status']=='completed' for s in version['steps']) else 'partial_test_failed',elapsed_seconds=round(time.monotonic()-start,2))
    state.update(status='stopped',stopped_at=datetime.now().astimezone().isoformat(),stage='F1 · 部分 시험 종료 · 품질 확인 대기');publish()
    save(OUT/'results.json',version)
    (OUT/'full-output.txt').write_text(version['text'],encoding='utf-8')
    print(json.dumps({k:v for k,v in version.items() if k not in ('text','steps')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
