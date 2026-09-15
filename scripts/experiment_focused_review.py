"""Post-generation table repair experiment, using original source bundles."""
import json,time,threading,sys,copy
from datetime import datetime
from pathlib import Path
import experiment_versions as e

def main(vid='v3'):
    e.STATE.update(json.loads((e.WEB/'experiment-monitor-state.json').read_text(encoding='utf-8')))
    version=next(v for v in e.STATE['versions'] if v['id']==vid);folder=e.OUT/vid
    start=time.monotonic();version['review_status']='running';version['status']='reviewing'
    generation_seconds=version['elapsed_seconds'];version['generation_seconds']=generation_seconds
    # Fixed numeric/customer tables are the known risk surface across companies.
    for key in e.api.app.VIEWS[:5]:
        if time.time()>=e.END:break
        path=folder/(key+'.result.json')
        if not path.exists():continue
        original=json.loads(path.read_text(encoding='utf-8'));req=json.loads((folder/(key+'.request.json')).read_text(encoding='utf-8'))
        body=json.loads(req['messages'][-1]['content']);props={}
        for i,t in enumerate(original.get('tables',[])):
            props[f't{i}']=e.obj({'rows':e.arr(e.arr({'type':['string','number','null']},len(t['columns']),len(t['columns'])),len(t['rows']),len(t['rows'])),'reason':e.TEXT})
        schema=e.obj(props)
        request={'model':e.api.app.config()['model'],'temperature':0.1,'max_tokens':4000,'chat_template_kwargs':{'enable_thinking':False},'structured_outputs':{'json':schema},'messages':[{'role':'system','content':e.BASE_RULES+'\n이미 모든 초안 생성이 끝났다. 이번 호출은 표만 검토한다. 원문과 기간·단위·행·열·연결/별도·추정 기준을 모두 대조한다. 확인되는 누락값만 보완한다. 행·열 수와 순서는 유지하며 부당한 변경을 하지 않는다. 동일한 기간·항목의 중복 상세는 하나만 유지하고 나머지 셀은 null로 비운다. 합계와 상세 금액이 맞는지 확인한다. 미확인 값은 0이나 다른 기간으로 대체하지 않는다. 원문 숫자가 %이고 표가 배이면 100으로 나눈다. 표 caption의 단위로 환산한다.'},{'role':'user','content':json.dumps({'tables':original.get('tables',[]),'documents':body['documents'],'sources':body['sources']},ensure_ascii=False)}]}
        count,maximum=e.api.token_count(request['messages'])
        if count+4512>maximum:
            version.setdefault('review_errors',[]).append(key+': 원문 보존 시 입력 예산 초과');continue
        step={'name':key+' · 표 집중 검토','status':'running','text':''};version['steps'].append(step);e.STATE['stage']=vid+' · '+step['name'];e.publish();beg=time.monotonic();last=[0]
        def progress(delta,text):
            if time.monotonic()-last[0]>1:step['text']=text;step['elapsed_seconds']=round(time.monotonic()-beg,2);e.publish();last[0]=time.monotonic()
        cancel=threading.Event();timer=e.deadline_timer(cancel)
        try:
            e.dump(folder/(key+'.focused.request.json'),request)
            response=e.api.llm_stream.complete(e.api.app.config(),request,progress,timeout=240,cancel_event=cancel);e.dump(folder/(key+'.focused.response.json'),response)
            if response['choices'][0]['finish_reason']!='stop':raise ValueError('불완전 응답')
            values=json.loads(response['choices'][0]['message']['content']);updated=copy.deepcopy(original)
            for i,t in enumerate(updated['tables']):
                rows=values[f't{i}']['rows'];assert len(rows)==len(t['rows']) and all(len(r)==len(t['columns']) for r in rows)
                if key!='customer_concentration':assert [r[0] for r in rows]==[r[0] for r in t['rows']]
                t['rows']=rows;t['review_reason']=values[f't{i}']['reason']
            e.dump(folder/(key+'.before-review.json'),original);e.dump(path,updated)
            step.update(status='completed',text=e.readable(updated),usage=response.get('usage'),input_tokens=count)
        except Exception as error:step.update(status='failed',error=str(error))
        finally:timer.cancel()
        step['elapsed_seconds']=round(time.monotonic()-beg,2);version['elapsed_seconds']=round(generation_seconds+time.monotonic()-start,2);e.publish()
    version['review_status']='completed' if len([s for s in version['steps'] if '집중 검토' in s['name'] and s['status']=='completed'])==5 else 'partial'
    version['status']='completed' if version['review_status']=='completed' and all(s['status']=='completed' for s in version['steps']) else 'partial'
    version['text']='\n\n'.join(e.readable(json.loads(p.read_text(encoding='utf-8'))) for p in sorted(folder.glob('*.result.json')))
    version['elapsed_seconds']=round(generation_seconds+time.monotonic()-start,2);e.dump(folder/'results.json',version);(folder/'full-output.txt').write_text(version['text'],encoding='utf-8');e.STATE['stage']=vid+' · 집중 검토 종료';e.publish()

if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'v3')
