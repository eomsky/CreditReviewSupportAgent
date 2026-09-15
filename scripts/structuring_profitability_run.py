"""Continuously measure fixed-table normalization, generation and materialization."""
import argparse,copy,hashlib,json,re,subprocess,sys,time,urllib.request
from pathlib import Path
from step_trial import initialize,trial
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--run-id',default='C20.17s-step3-r1');p.add_argument('--version',default='C20.17s');p.add_argument('--key',default='profitability',choices=['profitability','financial_stability']);p.add_argument('--parent',default='C20.13.1s-step2-replay');p.add_argument('--step',type=int,default=3);a=p.parse_args()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
began=time.perf_counter()
subprocess.run([sys.executable,'-X','utf8','scripts/structuring_ratio_step.py','--run-id',a.run_id,'--key',a.key,'--parent',a.parent,'--step',str(a.step)],cwd=root,check=True)
out=root/'outputs/step_trials'/a.run_id;base=root/'outputs/step_trials/C20.16s-step3-r1'
request=read(base/'generation.request.json');sources=read(base/'generation-sources.json');facts=read(out/'sql-facts.json')
if a.key=='financial_stability':
    request=read(root/'outputs/experiments/20260914/frozen/baseline_run/financial_stability.request.json')
    original_sources=json.loads(request['messages'][1]['content'])['sources']
    sources=[s for s in sources if json.loads(s['text']).get('table_type')!='profitability']
    sources.append({'id':'S5','document_id':facts[0]['source_id'].rsplit('-c',1)[0],'text':json.dumps({'table_id':a.key,'table_type':a.key,'basis':'unknown','columns':['account','period_label','period_role','unit','value']})})
    for i,s in enumerate(original_sources,6):sources.append({**s,'id':'S'+str(i)})
    request['structured_outputs']['json']['properties'].pop('fixed_tables');request['structured_outputs']['json']['required'].remove('fixed_tables')
    def update_ids(node):
        if isinstance(node,dict):
            if node.get('enum') and all(isinstance(x,str) and re.fullmatch('S[0-9]+',x) for x in node['enum']):node['enum']=[s['id'] for s in sources]
            for v in node.values():update_ids(v)
        elif isinstance(node,list):
            for v in node:update_ids(v)
    update_ids(request['structured_outputs'])
table_source=next(s for s in sources if s['id']=='S5')
table_payload=json.loads(table_source['text']);table_payload['rows']=[[f[k] for k in ('account','period_label','period_role','unit','value_decimal')] for f in facts];table_source['text']=json.dumps(table_payload,ensure_ascii=False)
payload=json.loads(request['messages'][1]['content']);payload['sources']=sources
payload['prepared_context']={'facts':[],'conflicts':[],'numeric_evidence':[],'quality_status':'numeric_normalization_only'}
payload['required_analysis']='매출 성장과 원가율/영업이익률 변화, 금융비용과 이자보상배율, 영업외손익 및 세전·법인세·순손익 연결, 추정 영업이익률/이자여력을 빠짐없이 분석한다. 당기순손실을 서술하면 요약에서도 법인세 영향을 누락하지 않는다. 원가율 차이는 %p로 표시한다. 원문 없는 원인 추측 금지.'
request['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
schema=request['structured_outputs']['json'];item=schema['properties']['analysis_paragraphs']['items']
topics={'revenue_and_costs':'매출증가율, 매출원가율 및 영업이익률의 당기/전기·동업계 비교와 의미','financial_burden':'금융비용부담률 및 이자보상배율의 추세와 상환부담','earnings_including_tax':'같은 손익계산서의 영업외손익·세전이익·법인세·순손익 수치를 연결하고 세전흑자에서 순손실이 되는 경우 법인세 영향을 명시','forecast':'추정 매출원가율·영업이익률·금융비용부담률·이자보상배율의 변화와 관리 필요'}
if a.key=='financial_stability':
    topics={'leverage':'부채비율·차입금의존도 추세와 동업계 대비 및 자본 완충력','liquidity':'유동비율과 비유동장기적합률로 단기유동성과 자금조달기간 불균형 분석','asset_quality':'매출채권·재고 비율 및 유형자산/차입금 추세를 분석하되 비율만으로 회수가능성·담보가치 확정 금지','forecast':'추정 재무안정성 지표와 실제 대비 개선/잔존위험·확인자료'}
    payload['required_analysis']='부채·유동성·자산의질·전망을 빠짐없이 분석한다. 실제0과 미확인0 여부가 불분명한 비율은 자산부재나 회수완료로 해석하지 않는다. 동일 기준 확인 없이 요약자산과 상세건물을 구성관계로 연결하지 않는다. 자본변동 원인을 손실로 확정하려면 직접 근거 필요. 만기연장은 원금부담 조정이며 이자상환 개선과 구분한다.'
    request['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
schema['properties']['analysis_paragraphs']={'type':'object','properties':{k:{**copy.deepcopy(item),'description':v} for k,v in topics.items()},'required':list(topics),'additionalProperties':False}
if a.key=='financial_stability':
    headings={'leverage':'부채 및 자본 완충력','liquidity':'단기 유동성과 조달기간','asset_quality':'자산 비율과 회수가능성 판단 한계','forecast':'재무안정성 전망과 확인사항'}
    for topic,heading in headings.items():
        paragraph_schema=schema['properties']['analysis_paragraphs']['properties'][topic]
        paragraph_schema['properties']['heading']={'type':'string','enum':[heading]}
        paragraph_schema['properties']['text']['description']=topics[topic]
    leverage=schema['properties']['analysis_paragraphs']['properties']['leverage']
    leverage['properties']={'capital_change_evidence_quote':{'type':['string','null'],'description':'자본 변동 원인을 직접 설명하는 원문 인용. 자본잔액·순손익·조정자본증가율만 있으면 null.'},**leverage['properties']}
    leverage['required']=['capital_change_evidence_quote',*leverage['required']]
    request['messages'][0]['content']+='\nleverage의 capital_change_evidence_quote가 null이면 자본 감소의 원인을 순손실 발생으로 확정하지 않는다. 자본 감소와 순손실 발생을 각각 기록하고 자본변동 상세 확인이 필요함을 명시한다. 이는 부채/자본 양측의 비율변화 분석을 생략하라는 뜻이 아니다.'
    schema['properties']={'asset_quality_support':{'type':'object','properties':{'direct_evidence_quote':{'type':['string','null']},'scope':{'type':'string','enum':['direct_evidence_available','ratios_only']}},'required':['direct_evidence_quote','scope'],'additionalProperties':False},**schema['properties']}
    schema['required']=['asset_quality_support',*schema['required']]
    asset=schema['properties']['analysis_paragraphs']['properties']['asset_quality']
    asset['properties']={'direct_quality_evidence_quote':{'type':['string','null'],'description':'연체/채권연령/재고체화/평가충당금 등 자산의 질 직접근거 원문 인용. 비율뿐이면 null. 원문 그대로 인용.'},**asset['properties']}
    asset['required']=['direct_quality_evidence_quote',*asset['required']]
    request['messages'][0]['content']+='\nasset_quality 문단은 먼저 direct_quality_evidence_quote로 직접 근거를 확인한다. 비율만 있으면 null이며 본문에 회수지연·체화 위험의 높고 낮음을 판단할 근거가 부족하다고 명시한다. 낮은 자산비중은 위험 낮음의 증거가 아니다. 비율의 관측과 자산의 질 판단을 분리하되 추세분석은 유지한다.'
    request['messages'][0]['content']+='\n먼저 asset_quality_support에서 근거 수준을 결정하고 요약과 네 본문 전체에 동일하게 적용한다. ratios_only이면 어느 문단에서도 체화/부실 징후가 낮음, 효율적 수준, 담보 여력이나 질적 담보 가치가 악화/충분함으로 결론내리지 않는다. 다른 문단에 단정을 남기고 뒤에 한계문장을 덧붙이는 것은 모순이므로 금지한다. 장부가액 대비 차입부담 변화만 분석하고 담보평가액·선순위채권·회수율 미확인을 밝힌다.'
    properties=schema['properties'];schema['properties']={k:properties[k] for k in ['asset_quality_support','title','analysis_paragraphs','paragraphs','required_document_reviews']}
    request['messages'][0]['content']+='\n상세 analysis_paragraphs를 먼저 작성하고 특이사항 paragraphs는 그 내용에서 확인된 관측만 요약한다. 요약에 새로운 원인이나 담보평가 판단을 추가하지 않는다. 자산대비 차입비율 변화는 장부상 비율 변화이며 담보 여력 변화라는 표현으로 대체하지 않는다.'
request['messages'][0]['content']+='\nanalysis_paragraphs는 네 논점별 문단 객체다. 모두 같은 최종 본문에 표시된다. 필수 논점과 근거 수치를 충분히 설명하되 다른 문단을 반복하지 않는다. 특이사항에서 적자 전환 원인을 요약할 때도 세전·법인세 영향을 정확히 보존한다.'
request['messages'][0]['content']+='\n고정표는 S5의 검수 SQL 수치로 프로그램이 출력한다. fixed_tables를 반환하지 않는 것은 표 생략이 아니다. 표의 모든 열과 행은 그대로 유지된다. 본문은 해당 절의 필수 논점을 중심으로 작성한다.'
if a.key=='financial_stability':
    request['messages'][0]['content']+='\n비유동장기적합률의 장기조달 재원은 자기자본과 비유동부채를 함께 포함한다. 장기부채만의 조달비율로 설명하지 않는다.'
original_system=request['messages'][0]['content'];seen=set();retained=[];duplicates=[]
for line in original_system.splitlines():
    normalized_line=line.strip()
    if len(normalized_line)>100 and normalized_line in seen:duplicates.append(line);continue
    retained.append(line);seen.add(normalized_line)
request['messages'][0]['content']='\n'.join(retained)
if set(original_system.splitlines())-set(retained):
    if any(line.strip() not in {v.strip() for v in retained} for line in duplicates):raise ValueError('Unique instruction removed')
save(out/'prompt-dedup-audit.json',{'original_chars':len(original_system),'deduplicated_chars':len(request['messages'][0]['content']),'removed_duplicate_lines':duplicates,'all_unique_instructions_preserved':True})
config=read(root/'workspace/llm_connection.json');endpoint=config['base_url'].rstrip('/');endpoint=endpoint[:-3] if endpoint.endswith('/v1') else endpoint
count=json.load(urllib.request.urlopen(urllib.request.Request(endpoint+'/tokenize',data=json.dumps({'model':config['model'],'messages':request['messages'],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}).encode(),headers={'Authorization':'Bearer '+config['api_key'],'Content-Type':'application/json'}),timeout=30))['count']
request['max_tokens']=min(8000,32768-count-512)
if request['max_tokens']<2000:raise ValueError('Insufficient output budget')
save(out/'generation.request.json',request);save(out/'generation-sources.json',sources);save(out/'budget-audit.json',{'input':count,'output':request['max_tokens'],'safety':512,'limit':32768})
initialize(out/'generation-trial',out/'generation.request.json',64)
result=trial(out/'generation-trial',root/'outputs/frozen_candidates/C20.4-step2-r1')
if result['status']=='fail':raise ValueError('Generation failed')
response=read(out/'generation-trial/attempt-001/response.json')
if response['choices'][0]['finish_reason']!='stop':raise ValueError('Incomplete generation')
body=json.loads(response['choices'][0]['message']['content']);body['paragraphs']+=list(body.pop('analysis_paragraphs').values())
for paragraph in body['paragraphs']:
    for field in ('direct_quality_evidence_quote','capital_change_evidence_quote'):
        quote=paragraph.get(field)
        if quote and not any(quote in source['text'] for source in sources):raise ValueError('Unsupported evidence quote')
if any(not v['source_ids'] or not set(v['source_ids'])<={s['id'] for s in sources} for v in body['paragraphs']):raise ValueError('Missing source')
raw=read(out/'original-table.json');title=raw[0];headers=[r['raw_value'] for r in raw if r['row_number']==title['row_number']+1];labels=list(dict.fromkeys(f['account'] for f in facts))
rows=[[label]+[next(f['value_decimal'] for f in facts if f['account']==label and f['period_label']==h) for h in headers[1:]] for label in labels]
body['tables']=[{'caption':title['raw_value'],'columns':headers,'rows':rows,'unit':re.search(r'단위:\s*([^)]*)',title['raw_value'])[1],'source_binding':{'source_id':title['source_id']},'after_paragraph_index':-1,'fixed_template':True}];body['sources']=sources
save(out/'materialized-artifact.json',body)
(out/'full-output.txt').write_text('\n'.join([body['title'],title['raw_value'],' | '.join(headers)]+[' | '.join(r) for r in rows]+['\n'+v['heading']+'\n'+v['text'] for v in body['paragraphs']]),encoding='utf-8')
elapsed=time.perf_counter()-began
save(out/'step-result.json',{'version':a.version,'step':a.step,'status':'completed','elapsed_seconds':elapsed,'target_seconds':70,'time_status':'pass' if elapsed<=70 else 'provisional_pass' if elapsed<=110 else 'fail','quality_status':'unassessed','allow_step'+str(a.step+1):False,'end_to_end':False,'scope':'continuous cached raw DB to normalization, SQL, generation, artifact; excludes original extraction/indexing'})
print(json.dumps(read(out/'step-result.json')))
