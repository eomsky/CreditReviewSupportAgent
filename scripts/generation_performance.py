"""Observe generation progress events without invoking the model or restarting the app."""
import hashlib
import json
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

BASE=Path(__file__).resolve().parents[1]
RUNS=BASE/'outputs'/'business_report_test'
DEST=BASE/'outputs'/'generation_performance'
LOCK=threading.Lock()


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def atomic(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temporary.replace(path)


def conditions(folder):
    data=json.loads((folder/'input.json').read_text(encoding='utf-8'))
    payload=data['payload']
    config=json.loads((BASE/'workspace'/'llm_connection.json').read_text(encoding='utf-8'))
    # No credentials, document text, or prompt text are written into performance logs.
    return {'requested_views':sorted(payload.get('target_views',['all'])),
            'review_level':payload.get('review_level',0),
            'documents_hash':digest(data['documents']),
            'instructions_hash':digest([payload.get(k) for k in ('common_prompt','generation_prompts','outline')]),
            'model':{k:config.get(k) for k in ('model','context_tokens')},
            'code_hash':digest({str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for pattern in ('scripts/*.py','prompts/*.txt') for p in BASE.glob(pattern)})}


def comparable_key(record):
    c={k:v for k,v in record['conditions'].items() if k!='code_hash'}
    return digest([c,record.get('schedule'),record.get('cache_hits'),record.get('cache_misses')])


def baseline(record,history):
    def eligible(r):
        return r.get('status')=='completed' and r.get('observed_from_start') and not r.get('observation_gap') and not r.get('concurrent_app_run')
    if not eligible(record):return None
    matches=[r for r in history if r['run_id']!=record['run_id'] and eligible(r)
             and comparable_key(r)==comparable_key(record) and r['elapsed_seconds']>0]
    if not matches:return None
    previous=max(matches,key=lambda r:r['started_at'])
    return {'run_id':previous['run_id'],'elapsed_seconds':previous['elapsed_seconds'],
            'change_percent':round((record['elapsed_seconds']/previous['elapsed_seconds']-1)*100,2)}


class Observation:
    def __init__(self,run_id,now=None):
        now=time.time() if now is None else now
        start=datetime.strptime(run_id[4:19],'%Y%m%d-%H%M%S').timestamp()
        self.record={'run_id':run_id,'started_at':datetime.fromtimestamp(start).astimezone().isoformat(),
                     'start_epoch':start,'observed_from_start':0<=now-start<=3,
                     'timing_method':'server run ID (1s precision) + progress SSE reception',
                     'observation_gap':False,'concurrent_app_run':False,'status':'running','stages':[]}
        self.last=now;self.stage=None

    def event(self,run,now=None):
        now=time.time() if now is None else now
        terminal=run.get('status') in ('completed','failed','cancelled')
        label=(run.get('phase','unknown'),run.get('stage','시작'))
        if self.stage is not None and (label!=self.stage or terminal):
            self.record['stages'].append({'phase':self.stage[0],'stage':self.stage[1],
                                           'elapsed_seconds':round(max(0,now-self.last),3)})
        if label!=self.stage or terminal:self.last=now;self.stage=label
        self.record.update(status=run.get('status','running'),schedule=run.get('target_views',[]),
                           elapsed_seconds=round(max(0,now-self.record['start_epoch']),3),
                           completed_calls=run.get('completed_calls',0),total_calls=run.get('total_calls'))
        if terminal:self.record['finished_at']=datetime.fromtimestamp(now).astimezone().isoformat()
        return terminal


def save(record):
    with LOCK:
        history=[]
        for path in DEST.glob('run-*.json'):
            if path.name.endswith('.live.json'):continue
            try:history.append(json.loads(path.read_text(encoding='utf-8')))
            except (OSError,ValueError):continue
        record['comparison']=baseline(record,history)
        atomic(DEST/(record['run_id']+'.json'),record)
        atomic(RUNS/record['run_id']/'performance.json',record)
        rows=sorted([r for r in history if r['run_id']!=record['run_id']]+[record],key=lambda r:r['started_at'],reverse=True)
        lines=['# 의견 생성 성능 기록','',
               '전체 서버 작업시간: 실행 ID의 시작시각부터 완료 이벤트 수신까지(초 단위 근사). 단계 시간은 관측한 구간만 포함한다.',
               '실패·중단·중간 합류·관측 공백·동시 앱 실행은 성능 비교에서 제외한다. 같은 자료·지침·모델·요청 범위·실제 작업 순서·검토 수준·캐시 조건의 완료 실행끼리 비교한다.',
               '외부에서 같은 모델에 요청한 부하는 자동 식별하지 못한다. 속도 변화는 관측값이며 코드 개선의 인과나 품질 향상을 뜻하지 않는다. 음수 변화율은 시간 단축이다.','',
               '| 실행 | 요청 범위 | 상태 | 전체 시간(초) | 이전 대비 | 시작부터 관측 |',
               '|---|---|---|---:|---:|---|']
        for r in rows[:100]:
            comparison=r.get('comparison');delta=f"{comparison['change_percent']:+.2f}%" if comparison else '비교 보류'
            lines.append(f"| {r['run_id']} | {', '.join(r['conditions']['requested_views'])} | {r['status']} | {r['elapsed_seconds']:.1f} | {delta} | {r['observed_from_start']} |")
        path=DEST/'PERFORMANCE.md';temporary=path.with_suffix('.tmp')
        temporary.write_text('\n'.join(lines)+'\n',encoding='utf-8');temporary.replace(path)


def watch(case_id,run_id,active):
    observation=Observation(run_id);record=observation.record
    try:
        record['conditions']=conditions(RUNS/run_id)
        for attempt in range(3):
            try:
                with urlopen('http://127.0.0.1:8766/api/credit-review/v1/events?case_id='+quote(case_id),timeout=30) as response:
                    for line in response:
                        if not line.startswith(b'data:'):continue
                        run=json.loads(line[5:])
                        if not run or run.get('id')!=run_id:raise ConnectionError('Run changed before terminal event')
                        record['concurrent_app_run'] |= len(active)>1
                        done=observation.event(run)
                        if done:
                            packets=[]
                            for p in (RUNS/run_id).rglob('*.preparation.json'):
                                try:packets.append(json.loads(p.read_text(encoding='utf-8')))
                                except (OSError,ValueError):pass
                            record['cache_hits']=sum(bool(p.get('cache_hit')) for p in packets)
                            record['cache_misses']=sum(not p.get('cache_hit',False) for p in packets)
                            save(record);return
                        atomic(DEST/(run_id+'.live.json'),record)
                raise ConnectionError('Progress stream ended early')
            except (OSError,ValueError):
                record['observation_gap']=True
                time.sleep(1)
        record['status']='observation_lost'
        record.setdefault('elapsed_seconds',round(time.time()-record['start_epoch'],3))
        save(record)
    except Exception as error:
        print(f'{run_id}: observer {type(error).__name__}',flush=True)
    finally:active.discard(run_id)


def main():
    # Singleton guard prevents duplicate event collectors after repeated server starts.
    guard=socket.socket();guard.bind(('127.0.0.1',8768));guard.listen(1)
    DEST.mkdir(parents=True,exist_ok=True);active=set()
    print('Generation performance observer started',flush=True)
    while True:
        for path in (RUNS/'cases').glob('*.json'):
            try:
                state=json.loads(path.read_text(encoding='utf-8'));run=state.get('run') or {};run_id=run.get('id','')
                if run.get('status')=='running' and run_id not in active and not (DEST/(run_id+'.json')).exists() and (RUNS/run_id/'input.json').exists():
                    active.add(run_id)
                    threading.Thread(target=watch,args=(state['id'],run_id,active),daemon=True).start()
            except (OSError,ValueError):continue
        time.sleep(1)


if __name__=='__main__':main()
