"""Bounded recovery for context limits and truncated structured generation."""
import copy
import json
from llm_stream import ContextLimitError, IncompleteStreamError


class CapacityError(ValueError):
    pass


def split_schema(schema):
    """Partition independent fields, or enumerated review/report items."""
    props=schema.get('properties',{})
    if len(props)>1:
        keys=list(props);middle=len(keys)//2
        return [{**copy.deepcopy(schema),'properties':{k:copy.deepcopy(props[k]) for k in part},
                 'required':[k for k in schema.get('required',[]) if k in part]}
                for part in (keys[:middle],keys[middle:])]
    if len(props)==1:
        key=next(iter(props));children=split_schema(props[key])
        if children:return [{**copy.deepcopy(schema),'properties':{key:child}} for child in children]
    if schema.get('type')=='array':
        item=schema.get('items',{});fields=item.get('properties',{})
        for key in ('paragraph_id','cell_id','title'):
            values=fields.get(key,{}).get('enum',[])
            if len(values)>1 and schema.get('minItems')==len(values) and schema.get('maxItems')==len(values):
                middle=len(values)//2;result=[]
                for group in (values[:middle],values[middle:]):
                    part=copy.deepcopy(schema);part['items']['properties'][key]['enum']=group
                    part['minItems']=part['maxItems']=len(group);result.append(part)
                return result
    return None


def merge(left,right):
    for key,value in right.items():
        if key not in left:left[key]=value
        elif isinstance(value,dict):merge(left[key],value)
        elif isinstance(value,list):left[key].extend(value)
        elif left[key]!=value:raise CapacityError('분할 생성 결과가 충돌하여 기존 의견을 보존했습니다.')
    return left


def complete(llm,config,payload,on_delta,token_count,timeout=360,cancel_event=None,on_recovery=None):
    request=copy.deepcopy(payload);calls=0;events=[]
    def notify(reason):
        events.append(reason)
        if on_recovery:on_recovery(reason)
    def run(req,depth=0,transport_retries=0):
        nonlocal calls
        if calls>=24 or depth>8:raise CapacityError('자동 분할 조정 한도에 도달했습니다. 완료된 의견은 보존되어 있습니다.')
        count,maximum=token_count(req['messages'])
        available=maximum-count-512
        if available<1024:
            # Retain every source ID/document and original wording; omit only optional prior AI drafts.
            body=json.loads(req['messages'][-1]['content'])
            body.pop('prior_model_drafts',None)
            for limit in (1000,600,300,150):
                for field in ('sources','compressed_sources'):
                    for source in body.get(field,[]):
                        text=source.get('text','')
                        if len(text)>limit:source['text']=text[:limit]+'\n[발췌 일부]'
                req['messages'][-1]['content']=json.dumps(body,ensure_ascii=False)
                count,maximum=token_count(req['messages']);available=maximum-count-512
                if available>=1024:break
            notify('입력 한도 조정: 원문 ID와 필수 자료를 유지하며 발췌량 조절')
        if available<1024:raise CapacityError('시스템 지침과 본문만으로 모델 한도를 초과하여 자동 조정을 완료하지 못했습니다. 기존 의견은 보존됩니다.')
        # Partition a large response before spending time on a predictably tiny
        # output window. Independent fields are merged only after all succeed.
        parts=split_schema(req['structured_outputs']['json']) if depth==0 and req['max_tokens']>=6000 and available<4096 else None
        if parts:
            combined={}
            for index,part in enumerate(parts):
                child=copy.deepcopy(req);child['structured_outputs']['json']=part
                child['messages'][0]['content']+='\n사전 분할: 이번 JSON 스키마의 필드만 완결하여 반환한다. 나머지는 별도 호출에서 처리한다.'
                notify(f'사전 분할 처리 {index+1}/{len(parts)}')
                result=run(child,depth+1)
                merge(combined,json.loads(result['choices'][0]['message']['content']))
            return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps(combined,ensure_ascii=False)}}]}
        if req['max_tokens']>available:
            req['max_tokens']=available
            notify('입력·출력 예산 자동 조정')
        calls+=1
        try:
            response=llm.complete(config,req,on_delta,timeout=timeout,cancel_event=cancel_event)
        except IncompleteStreamError:
            if transport_retries>=1:raise
            notify('응답 연결 중단: 현재 검토만 다시 요청')
            return run(req,depth,transport_retries+1)
        except ContextLimitError:
            if depth>=3:raise CapacityError('서버 문맥 한도가 반복해서 불일치합니다. 완료된 의견은 보존됩니다.')
            req['max_tokens']=max(512,req['max_tokens']//2)
            body=json.loads(req['messages'][-1]['content']);body.pop('prior_model_drafts',None)
            for field in ('sources','compressed_sources'):
                for source in body.get(field,[]):
                    text=source.get('text','');limit=max(150,int(len(text)*0.6))
                    if len(text)>limit:source['text']=text[:limit]+'\n[발췌 일부]'
            req['messages'][-1]['content']=json.dumps(body,ensure_ascii=False)
            notify('서버 한도 초과: 발췌량과 출력 예약량을 줄여 재시도')
            return run(req,depth+1)
        if response['choices'][0].get('finish_reason')!='length':return response
        notify('응답 길이 초과: 잘린 응답을 폐기하고 생성 단위 조정')
        # Try a larger response once when the context has spare capacity.
        if req['max_tokens']<available:
            req['max_tokens']=min(available,max(req['max_tokens']+2048,req['max_tokens']*2))
            return run(req,depth+1)
        parts=split_schema(req['structured_outputs']['json'])
        if not parts:raise CapacityError('최소 생성 단위도 출력 한도를 초과했습니다. 기존 의견은 보존되어 있습니다.')
        combined={}
        for index,schema in enumerate(parts):
            child=copy.deepcopy(req);child['structured_outputs']['json']=schema
            child['messages'][0]['content']+='\n자동 분할 생성: 이번 응답은 지정된 JSON 스키마의 필드와 열거된 항목만 완결하여 반환한다. 다른 항목은 별도 호출에서 처리한다. 원문 근거와 기존 본문을 기준으로 판단한다.'
            notify(f'분할 처리 {index+1}/{len(parts)}')
            result=run(child,depth+1)
            merge(combined,json.loads(result['choices'][0]['message']['content']))
        return {'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(combined,ensure_ascii=False)}}], 'recovery':events}
    result=run(request)
    if events:result['recovery']=events
    if on_recovery:on_recovery('')
    return result
