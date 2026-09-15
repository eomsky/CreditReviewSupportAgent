"""Select accepted interpretations rather than regenerating their causal claims."""
import copy,json
from decimal import Decimal
from pathlib import Path

def main():
    root=Path(__file__).resolve().parents[1]
    parent=root/'outputs/step_trials/C20.30.2-step13-input'
    out=root/'outputs/step_trials/C20.30.3-step13-input';out.mkdir(exist_ok=False)
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    save=lambda p,d:p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    req=read(parent/'generation.request.json');payload=json.loads(req['messages'][1]['content'])
    catalog={}
    for si,section in enumerate(payload['prior_model_drafts'].values()):
        for pi,p in enumerate(section['paragraphs']):
            catalog[f'A{si+1}P{pi+1}']=copy.deepcopy(p)
    fixtures=read(parent/'table-fixtures.json')
    suppliers=fixtures['사업성'][0]
    for row in suppliers['rows']:
        row[1]=int(row[1]) if float(row[1]).is_integer() else row[1]
    top=sorted(suppliers['rows'],key=lambda r:r[1],reverse=True)[:3]
    total=sum(Decimal(str(row[2])) for row in top)
    names=', '.join(f'{row[0]}({row[2]}%)' for row in top)
    catalog['SQL_PURCHASE']={'heading':'','text':f"2025년 주요 매입처 중 거래대금 상위 3개 업체는 {names}이며, 기재된 비중의 합은 {total}%임. 매입처별 거래조건과 대체조달 가능성에 대한 확인이 필요함.",'source_ids':suppliers['source_ids'],'origin':'source-exact SQL aggregate plus explicit follow-up, not approved prior interpretation'}
    # This source-bound statement is auditable; it does not assign a meaning to 0.
    source=next(s for s in read(parent/'original-source-archive.json') if s['id']=='S1')
    lines=source['text'].splitlines();header=next(i for i,v in enumerate(lines) if '제품명 | 시장점유율 | 주요경쟁업체' in v)
    product,share,competitors=[v.strip() for v in lines[header+1].split('|')]
    catalog['SOURCE_MARKET']={'heading':'','text':f'시장현황 표에 기재된 {product}의 주요 경쟁업체는 {competitors}임. 시장점유율 기재값은 {share}%이나 산정 기준이 확인되지 않아 시장 지위 판단에는 한계가 있음.','source_ids':['S1'],'origin':'source-exact transcription plus unresolved basis'}
    roles={'establishment':'설립 경위와 주력사업','history':'주요 합병 및 분할 연혁','management':'대표자 경력과 경영체제','ownership':'주주 구성','affiliates':'종속회사와 관계사 분석 한계','business_model':'제품과 사업모델','sales':'최근 매출 및 사업 실적','customers':'고객집계 사실과 분석 한계','purchases':'SQL 상위 매입처 비중 및 거래조건 확인','market':'원문 경쟁업체와 점유율 산정기준 한계'}
    payload['reuse_catalog']=catalog;payload['required_reuse_roles']=roles
    schema=req['structured_outputs']['json'];schema['properties']['sections']['items']['properties']['paragraphs']={'type':'array','items':{'type':'object','properties':{'role':{'type':'string','enum':list(roles)},'reuse_id':{'type':'string','enum':list(catalog)}},'required':['role','reuse_id'],'additionalProperties':False},'minItems':4,'maxItems':7}
    req['messages'][1]['content']=json.dumps(payload,ensure_ascii=False)
    req['messages'][0]['content']+='\n본문을 새로 쓰지 않고 reuse_catalog의 문단 ID를 선택한다. 프로그램이 원문 문장과 출처를 그대로 연결한다. 업체개요는 establishment/history/management/ownership/affiliates, 사업성은 business_model/sales/customers/purchases/market 역할을 각각 빠짐없이 채운다. 같은 문단의 중복 선택은 금지한다. purchases는 SQL_PURCHASE, market은 SOURCE_MARKET을 선택하고 나머지는 역할에 맞는 승인문단을 선택한다. 서로 다른 작성기준을 섞거나 원문에 없는 인과를 추가하지 않는다. 출처·목차·분석범위의 품질 요구사항은 그대로 적용된다.'
    save(out/'reuse-catalog.json',catalog);save(out/'generation.request.json',req);save(out/'table-fixtures.json',fixtures)
    for name in ['original-source-archive.json','lineage.json','source-encoding-audit.json','table-source-audit.json','table-facts.sqlite']:(out/name).write_bytes((parent/name).read_bytes())
    print(out)

if __name__=='__main__':main()
