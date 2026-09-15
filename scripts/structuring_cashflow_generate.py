"""Generate cashflow commentary from approved SQL, preserving both fixed tables."""
import copy, hashlib, json, re, sqlite3, sys, time, urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from step_trial import initialize, trial
from section_prompt_router import route
from cashflow_bridge import from_source

root = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
save = lambda p,v: p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')


def main():
    began=time.perf_counter()
    main_dir=root/'outputs/step_trials/C20.24.4s-step7-main'
    cash_dir=root/'outputs/step_trials/C20.24.3s-step7-normalization'
    out=root/'outputs/step_trials/C20.24.12s-step7-r1';out.mkdir(exist_ok=False)
    gate=read(root/'outputs/step_trials/C20.24s-step6-r1/step-result.json')
    if not gate.get('allow_step7') or gate['quality_status']!='pass':raise ValueError('Step6 not accepted')
    for name,h in gate['artifact_sha256'].items():
        if hashlib.sha256((root/'outputs/step_trials/C20.24s-step6-r1'/name).read_bytes()).hexdigest()!=h:raise ValueError('Parent changed')
    manifest=read(cash_dir/'approval-manifest.json')
    for name,h in manifest['hashes'].items():
        if hashlib.sha256((cash_dir/name).read_bytes()).hexdigest()!=h:raise ValueError('Cashflow approval changed')
    import approved_table_cache
    approved_table_cache.validate(main_dir)
    facts=read(main_dir/'sql-facts.json')
    with sqlite3.connect((cash_dir/'numeric.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        cash=[dict(r) for r in db.execute('SELECT * FROM cashflow_facts ORDER BY account,period')]
    req=read(root/'outputs/experiments/20260914/frozen/baseline_run/cashflow_repayment.request.json')
    payload=json.loads(req['messages'][1]['content']);sources=payload['sources']
    sources += [{'id':'S12','document_id':facts[0]['source_id'].rsplit('-c',1)[0],
                 'text':json.dumps({'table_type':'cashflow_repayment','basis':'unknown','approved_facts':facts},ensure_ascii=False)},
                {'id':'S13','document_id':cash[0]['document_id'],
                 'text':json.dumps({'table_type':'statutory_cashflow','basis':'consolidated','approved_facts':cash},ensure_ascii=False)}]
    payload['prepared_context']={'facts':[],'conflicts':[],'numeric_evidence':[],'quality_status':'SQL_normalization_approved'}
    payload.pop('prior_model_drafts',None)
    payload['required_analysis']='고정 상환능력표는 S12, 연결 현금흐름표는 S13을 기준으로 읽는다. S3/S8의 상세 재무현황과 S12의 종합의견 수치가 다르면 서로 대체하거나 동일 지표로 혼합하지 말고 출처 및 산식/작성기준 차이 확인 필요성을 밝힌다. 현금흐름표는 2024/2025만 확인됐으며 2023 수치는 추측하지 않는다. 원문 원 단위와 SQL 백만원을 이중 변환하지 않는다. 추정1기의 현금흐름 및 상환후 부족액을 분석하고, 원금상환과 이자부담을 구분한다.'
    bridge=from_source(next(source for source in sources if source['id']=='S10'))
    if not bridge['flow_reconciles'] or not bridge['balance_reconciles']:raise ValueError('Forecast bridge mismatch')
    payload['forecast_bridge']=bridge
    repayment_observations=[{'period':f['period_label'],'role':f['period_role'],'balance':f['value_decimal'],'sign':'surplus' if Decimal(f['value_decimal'])>0 else 'deficit' if Decimal(f['value_decimal'])<0 else 'balanced'} for f in facts if f['account']=='유동성장기부채상환후CF']
    payload['repayment_observations']=repayment_observations
    save(out/'forecast-bridge.json',bridge)
    req['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
    schema=req['structured_outputs']['json'];schema['properties'].pop('fixed_tables');schema['required'].remove('fixed_tables')
    schema['properties']={'forecast_bridge_review':{'type':'string','enum':['supported','unresolved']},**schema['properties']}
    schema['required'].insert(0,'forecast_bridge_review')
    item=schema['properties']['analysis_paragraphs']['items']
    topics={'operating_cash':'영업·이자지급 후 CF 및 실제 상환후 자금잉여/부족 추세',
            'investment_financing':'연결 현금흐름표에서 영업/투자/재무CF와 기말현금의 흐름. 작성기준이 다른 수치 혼합 금지',
            'repayment':'EBITDA·금융비용·차입부담·이자보상/순부채상환 지표의 추세와 원금/이자 부담 구분',
            'forecast':'추정 CF/상환후 부족 및 상환지표로 전망, 조달계획 등 확인할 근거'}
    schema['properties']['analysis_paragraphs']={'type':'object','properties':{k:{**copy.deepcopy(item),'description':v} for k,v in topics.items()},'required':list(topics),'additionalProperties':False}
    for topic,description in topics.items():
        part=schema['properties']['analysis_paragraphs']['properties'][topic]
        part['properties']['heading']={'type':'string','enum':[{'operating_cash':'신용조사서 기준 현금흐름과 상환재원','investment_financing':'연결 현금흐름과 투자·조달','repayment':'현금창출 대비 원리금 상환부담','forecast':'추정 상환능력과 확인사항'}[topic]]}
        part['properties']['text']['description']=description
    req['messages'][0]['content']+='\n현금흐름 해석 검수: 감가상각비 등 비현금 조정은 순손익에서 영업현금흐름으로 조정하는 가산/차감이며 그 자체가 현금 유입을 발생시키지 않는다. 예: 순손실10에 비현금비용30을 가산한 것은 현금30을 받은 것이 아니다. 운영자산부채 증감 등도 함께 구분한다. operating_cash는 S12의 실제 영업후/이자후/상환후CF 추세를 반드시 분석하고, investment_financing에서 S13 연결CF를 별도로 다룬다. 서로 다른 출처의 이자지급액/금융비용과 EBITDA를 섞어 배수를 만들지 않는다. 추정 분석은 S12의 추정열과 S10의 조달/상환 정보를 함께 대조한다. 위 예시 수치는 현재기업에 사용하지 않는다.'
    def update(node):
        if isinstance(node,dict):
            if node.get('enum') and all(isinstance(x,str) and re.fullmatch('S[0-9]+',x) for x in node['enum']):node['enum']=[s['id'] for s in sources]
            if node.get('type')=='array' and 'source_ids' not in node and node.get('items',{}).get('enum'):node['maxItems']=len(node['items']['enum'])
            for v in node.values():update(v)
        elif isinstance(node,list):
            for v in node:update(v)
    update(schema)
    req['messages'][0]['content']+='\n문단별 근거 범위: operating_cash는 신용조사서 S12의 실제 3개년 영업후/이자후/상환후CF만 분석한다. 연결CF와의 대조가 필요하면 별도 연결문단에서 작성기준이 다름을 명시한다. forecasting에서 외부조달전CF→차입/자본 증감→외부조달후CF→기초/기말 현금의 순서를 원문 행 제목으로 확인한다. 원금상환후 적자를 이미 신규차입 포함한 부족액으로 설명하지 않는다. CF가 음수여도 기초현금으로 충당 가능한지 확인 없이 현금부족/지급불능으로 단정하지 않는다. 원문 조달계획은 확약이 아니므로 실현가능성 확인 조건을 제시한다. 예시: 조달전-100, 신규차입60, 조달후-40, 기초현금80이면 기말40이다. 신규차입 포함 부족액이100이라거나 지급불능이라 쓰지 않는다. 예시숫자 복사 금지.'

    req['messages'][0]['content']+='\n고정표 2개는 SQL로 출력하므로 fixed_tables는 반환하지 않는다. analysis_paragraphs는 네 논점별 객체로 충분한 해석을 유지한다. 본문 문단별 source_ids는 중복없이 기록한다. 작성기준 미확정 수치들을 섞어 계산하거나 원인으로 확정하지 않는다.'
    req['messages'][0]['content']+='\n인용 검수: 은행별 차입잔액은 S1 원문에 있으므로 이를 언급하면 S1을 함께 인용한다. S12는 상환능력 SQL지표만 포함한다. 차입금/EBITDA는 현금창출 대비 차입부담 지표이며, 실제 계약상 만기나 상환기간이 늘었다는 직접 증거가 아니다. 해당 비율 상승은 상환부담 증가로 설명하고 계약만기 변화로 확정하지 않는다.'
    req['messages'][0]['content']+='\nforecast_bridge는 원문 조달행과 기초/기말 잔액을 대조한 후보 계산이다. 먼저 기간/행의 의미를 S10과 검수해 forecast_bridge_review를 판정한다. supported이면 forecast 본문에서 조달전CF, 조달후CF, 기초현금, 기말현금을 구분한다. 기초현금은 조달후CF에 포함되지 않으며 조달후CF에 더해 기말잔액을 계산한다. 기초현금과 신규차입을 포함한 조달후CF라는 문장은 틀리다. 기말잔액과 조달계획 실현조건을 함께 설명한다.'
    req['messages'][0]['content']+='\n모든 제공 출처를 인용할 수 있으나 해당 수치가 실제 존재하는 출처를 선택한다. 연결 이자 지급액은 S6, 은행별 잔액은 S1, 고정지표는 S12다. 동일 문단에서 출처기준이 달라지면 명시하고 서로 합산하지 않는다. 순부채상환계수 등 정의/산식이 없는 지표는 추세와 확인필요성만 설명하며 1 미만이라는 이유만으로 해당기간 원리금 상환이 불가능하다고 확정하지 않는다. 실제 상환후CF/보유현금 및 만기/조달계획을 함께 대조한다. 확인되지 않은 정의를 일반적 의미로 보충하지 않는다.'
    req['messages'][0]['content']+='\n상환후CF 부호 검수: repayment_observations에서 실적연도별 잉여/부족과 추정을 분리한다. 최신 실적이 흑자면 과거 적자만을 근거로 최신 원금상환이 불가능/감당어려움이라고 쓰지 않는다. 흑자폭과 잔존위험을 설명한다. 차입금/EBITDA 비율 상승에는 분자 증가뿐 아니라 분모 감소도 영향을 주므로 EBITDA추세 확인 없이 현금창출력이 증가했다고 전제하지 않는다. 두 값의 변화와 비율의 의미를 분리한다.'
    original_system=req['messages'][0]['content']
    req['messages'][0]['content'],routing_audit=route(original_system,'cash_flow')
    save(out/'prompt-routing-audit.json',routing_audit)
    config=read(root/'workspace/llm_connection.json');endpoint=config['base_url'].rstrip('/');endpoint=endpoint[:-3] if endpoint.endswith('/v1') else endpoint
    count=json.load(urllib.request.urlopen(urllib.request.Request(endpoint+'/tokenize',data=json.dumps({'model':config['model'],'messages':req['messages'],'add_generation_prompt':True,'chat_template_kwargs':{'enable_thinking':False}}).encode(),headers={'Authorization':'Bearer '+config['api_key'],'Content-Type':'application/json'}),timeout=30))['count']
    models=json.load(urllib.request.urlopen(urllib.request.Request(config['base_url'].rstrip('/')+'/models',headers={'Authorization':'Bearer '+config['api_key']}),timeout=30))
    limits=[m.get('max_model_len',32768) for m in models['data'] if m.get('id')==config['model']]
    limit=min(65536,limits[0] if limits else 32768)
    req['max_tokens']=min(8000,limit-count-512)
    if req['max_tokens']<2000:raise ValueError('Insufficient output budget')
    save(out/'generation.request.json',req);save(out/'generation-sources.json',sources)
    save(out/'budget-audit.json',{'input':count,'output':req['max_tokens'],'limit':limit,'safety':512})
    initialize(out/'generation-trial',out/'generation.request.json',70)
    result=trial(out/'generation-trial',root/'outputs/frozen_candidates/C20.4-step2-r1',timeout=120)
    if result['status']=='fail':save(out/'failure.json',result);return
    body=json.loads(read(out/'generation-trial/attempt-001/response.json')['choices'][0]['message']['content'])
    if body.get('forecast_bridge_review')!='supported':raise ValueError('Forecast semantics unresolved')
    body['paragraphs']+=list(body.pop('analysis_paragraphs').values())
    if any(not p['source_ids'] or not set(p['source_ids'])<={s['id'] for s in sources} for p in body['paragraphs']):raise ValueError('Invalid citations')
    raw=read(main_dir/'original-table.json');title=raw[0];headers=[r['raw_value'] for r in raw if r['row_number']==title['row_number']+1]
    labels=list(dict.fromkeys(f['account'] for f in facts))
    main_rows=[[label]+[next(f['value_decimal'] for f in facts if f['account']==label and f['period_label']==h) for h in headers[1:]] for label in labels]
    cash_rows=[]
    for name,label in [('operating_cashflow','영업활동으로 인한 현금흐름'),('investing_cashflow','투자활동으로 인한 현금흐름'),('financing_cashflow','재무활동으로 인한 현금흐름'),('closing_cash','기말 현금및현금성자산')]:
        cash_rows.append([label]+[next((str(Decimal(f['value_decimal']).quantize(Decimal(1),rounding=ROUND_HALF_UP)) for f in cash if f['account']==name and f['period']==y),'—') for y in ['2023','2024','2025']])
    body['tables']=[{'caption':title['raw_value'],'columns':headers,'rows':main_rows,'unit':'백만원, 배','source_binding':{'source_id':'S12'},'after_paragraph_index':-1,'fixed_template':True},
                    {'caption':'현금흐름표 (단위: 백만원)','columns':['과목','2023년','2024년','2025년'],'rows':cash_rows,'unit':'백만원','source_binding':{'source_id':'S13'},'after_paragraph_index':-1,'fixed_template':True}]
    body['sources']=sources;save(out/'materialized-artifact.json',body)
    (out/'full-output.txt').write_text('\n'.join([body['title']]+[t['caption']+'\n'+' | '.join(t['columns'])+'\n'+'\n'.join(' | '.join(row) for row in t['rows']) for t in body['tables']]+['\n'+p['heading']+'\n'+p['text'] for p in body['paragraphs']]),encoding='utf-8')
    elapsed=time.perf_counter()-began
    save(out/'step-result.json',{'version':'C20.24.12s','step':7,'status':'completed','elapsed_seconds':elapsed,'target_seconds':70,'time_status':'unassessed','quality_status':'unassessed','allow_step8':False,'end_to_end':False,'scope':'generation using previously approved normalization; full cold-step time not measured','prior_normalization_seconds':read(main_dir/'preparation-result.json')['elapsed_seconds']+3.781})
    print(json.dumps(read(out/'step-result.json')))


if __name__=='__main__':main()
