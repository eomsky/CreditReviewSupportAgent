"""Two-worker replay of a frozen request design, rebuilding report priors from this run."""
import json,time,copy,threading,shutil,sys
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
import experiment_versions as e

def main(source='v4',vid='v5',workers=2,enriched=False,reuse=None):
    e.STATE.update(json.loads((e.WEB/'experiment-monitor-state.json').read_text(encoding='utf-8')))
    version={'id':vid,'description':source+f'의 입력·양식 + {workers}개 동시 처리'+(' + 보고서 공통 원문 재사용' if enriched else ''),'status':'running','started_at':datetime.now().astimezone().isoformat(),'steps':[],'text':''};e.STATE['versions'].append(version)
    folder=e.OUT/vid;folder.mkdir(exist_ok=True);original=e.OUT/source;lock=threading.RLock();start=time.monotonic();prior={}
    keys=e.api.app.VIEWS+['report_1','report_2','report_3']
    if reuse:
        version['description']+=' · '+reuse+' 의견 재사용 부분실험';version['measurement_scope']='report_only_with_reused_opinions';version['reused_version']=reuse
        for key in keys[:6]:
            for suffix in ['result','sources']:
                shutil.copy2(e.OUT/reuse/(key+'.'+suffix+'.json'),folder/(key+'.'+suffix+'.json'))
            prior[key]=json.loads((folder/(key+'.result.json')).read_text(encoding='utf-8'));version['steps'].append({'name':key,'status':'reused','elapsed_seconds':0,'text':e.readable(prior[key])})
    e.dump(folder/'configuration.json',{'source_version':source,'workers':workers,'enriched_report_sources':enriched,'reuse':reuse,'phase_barrier':'all opinions before reports','model':e.api.app.config()['model']})
    def update():
        version['elapsed_seconds']=round(time.monotonic()-start,2);version['text']='\n\n'.join('【'+s['name']+'】\n'+s.get('text','') for s in version['steps']);e.dump(folder/'results.json',version);e.publish()
    def task(key):
        if time.time()>=e.END:return
        req=json.loads((original/(key+'.request.json')).read_text(encoding='utf-8'));body=json.loads(req['messages'][-1]['content'])
        evidence=json.loads((original/(key+'.sources.json')).read_text(encoding='utf-8'))
        if key.startswith('report'):
            body['prior_drafts']={k:v for k,v in prior.items() if k in ['summary_2','profitability','cashflow_repayment']}
            if enriched:
                names=' '.join(body['sections']);related=[]
                for view,words in [('cashflow_repayment',['상환','현금','종합']),('profitability',['수익','종합']),('financial_stability',['재무','보전']),('summary_2',['개요','사업'])]:
                    if any(w in names for w in words):related.append(view)
                picked=[]
                for view in related:picked.extend(json.loads((folder/(view+'.sources.json')).read_text(encoding='utf-8')))
                evidence=list({s['id']:s for s in picked+evidence}.values())
                def strip_refs(v):
                    if isinstance(v,dict):return {k:strip_refs(x) for k,x in v.items() if k!='source_ids'}
                    if isinstance(v,list):return [strip_refs(x) for x in v]
                    return v
                body['prior_drafts']=strip_refs(body['prior_drafts'])
                req['messages'][0]['content']+='\n앞선 의견에 사용한 공통 원문이 함께 제공된다. 원문상 현금흐름표와 분석용 조정 현금흐름은 서로 다른 지표이며 대체하지 않는다. 항목 간 다른 기준은 설명하고 동일한 기준의 수치를 일관되게 사용한다. 이전 초안의 별칭은 근거가 아니므로 이번 sources에서 실제 인용을 고른다.'
        req['messages'][-1]['content']=json.dumps(body,ensure_ascii=False)
        step={'name':key,'status':'running','text':''};beg=time.monotonic();first=[None];last=[0]
        with lock:version['steps'].append(step);e.STATE['stage']=vid+f' · {workers}개 작업 동시 생성';update()
        cancel=threading.Event();timer=e.deadline_timer(cancel)
        def progress(delta,text):
            if first[0] is None:first[0]=time.monotonic()
            if time.monotonic()-last[0]>2:
                with lock:step['text']=text;step['elapsed_seconds']=round(time.monotonic()-beg,2);update()
                last[0]=time.monotonic()
        try:
            while True:
                if enriched and key.startswith('report'):
                    body['sources']=[{'id':f'S{i+1}','document_id':s['document_id'],'text':e.api.prepared_context.prompt_source_text(s)} for i,s in enumerate(evidence)]
                    req['messages'][-1]['content']=json.dumps(body,ensure_ascii=False)
                count,maximum=e.api.token_count(req['messages'])
                if count+req['max_tokens']+512<=maximum:break
                if not enriched or len(evidence)<=1:raise ValueError('출력 공간 부족')
                evidence.pop()
            if enriched and key.startswith('report'):
                def aliases(node):
                    if isinstance(node,dict):
                        if 'source_ids' in node.get('properties',{}):node['properties']['source_ids']['items']['enum']=[s['id'] for s in body['sources']]
                        for v in node.values():aliases(v)
                    elif isinstance(node,list):
                        for v in node:aliases(v)
                aliases(req['structured_outputs']['json'])
            e.dump(folder/(key+'.request.json'),req);e.dump(folder/(key+'.sources.json'),evidence)
            r=e.api.llm_stream.complete(e.api.app.config(),req,progress,timeout=360,cancel_event=cancel);e.dump(folder/(key+'.response.json'),r)
            if r['choices'][0]['finish_reason']!='stop':raise ValueError('출력 미완결')
            result=json.loads(r['choices'][0]['message']['content'])
            if key in e.api.app.VIEWS[:5]:e.api.fixed_review_tables.apply(result,key);result['title']=body['sections'][0]
            e.dump(folder/(key+'.result.json'),result)
            with lock:prior[key]=result;step.update(status='completed',text=e.readable(result),usage=r.get('usage'),input_tokens=count,first_token_seconds=round(first[0]-beg,3) if first[0] else None)
        except Exception as error:
            with lock:step.update(status='failed',error=str(error))
        finally:
            timer.cancel()
            with lock:step['elapsed_seconds']=round(time.monotonic()-beg,2);update()
    for group in ([keys[6:]] if reuse else [keys[:6],keys[6:]]):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for f in as_completed([pool.submit(task,k) for k in group]):f.result()
    version['steps'].sort(key=lambda s:keys.index(s['name']));version['status']=('partial_experiment_completed' if reuse else 'completed') if len(version['steps'])==9 and all(s['status'] in ['completed','reused'] for s in version['steps']) else 'partial';e.STATE['stage']=vid+' · 동시 생성 종료'
    with lock:update()
    (folder/'full-output.txt').write_text(version['text'],encoding='utf-8')

if __name__=='__main__':main('v4',sys.argv[1] if len(sys.argv)>1 else 'v5',int(sys.argv[2]) if len(sys.argv)>2 else 2,'enriched' in sys.argv,sys.argv[sys.argv.index('--reuse')+1] if '--reuse' in sys.argv else None)
