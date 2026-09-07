"""Repair supplied synthetic SFT records, preserve splits, emit runtime contracts.

Original bytes stay untouched. Every exclusion and repair is written to an audit.
This does not turn synthetic examples into real bank policy or expert gold labels.
"""
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import re
import zipfile

EXPECTED_SHA='89b094d47b0238cd43b46728fc3e7a5e757bb4d33a0a555416c748bc91b6cedc'
SYSTEM=('기업여신 심사역으로서 제공된 근거와 검증된 계산만 사용한다. '
        '사실, 원인 또는 대안적 해석, 현금흐름과 상환능력 영향을 연결한다. '
        '지원능력·지원의사·법적 보증, 이익·현금흐름, 기존 약정·신청조건을 구분한다. '
        '미제공 사실은 만들지 않으며 중요한 판단 조건은 의견에 명시한다. '
        '내부 사고 전문 대신 검증 가능한 근거 요약과 결론을 작성한다.')

CAUSAL={
 'F03':'지원여력 지수만으로 주주의 실제 자금지원이나 법적 보증을 인정할 수 없다. 배당은 차주의 유동성 유출과 연결되므로 지원약정 및 배당 후 현금흐름을 구분하여 평가한다.',
 'F04':'재임기간은 경영의 연속성을 보여주지만 경영능력이나 내부통제의 실효성을 단독으로 입증하지 않는다. 주요 인력 의존도와 승계·통제 체계가 사업 지속성에 미치는 영향을 함께 고려한다.',
 'F05':'종속기업 수만으로 계열 지원부담이 작다고 판단할 수 없다. 종속기업 손익·차입금·지급보증·차주와의 자금거래가 제공되지 않아 지원에 따른 현금유출 규모는 특정할 수 없다.',
 'F06':'주력제품 수요 변동은 매출과 현금유입에 직접 전이된다. 제품 집중도만으로 감내 가능성을 단정하지 않고 대체 제품과 매출처, 고정비 부담을 함께 판단한다.',
 'F07':'점유율은 현재 판매 기반을 보여주지만 진입장벽과 가격 결정력은 별도로 평가해야 한다. 경쟁 심화 시 단가와 마진이 낮아질 수 있어 현재 점유율을 미래 수익성으로 단정하지 않는다.',
 'F09':'현재 순위와 점유율은 시장 내 위치의 근거이나 지속적인 안정성을 보장하지 않는다. Peer와의 수익성·차입부담 차이가 가격경쟁 및 투자여력에 미치는 영향을 함께 고려한다.',
 'F10':'계약 잔존기간은 매출 지속성의 보완 요인이지만 최소물량이나 대금회수를 보장하는 조건과 동일하지 않다. 주요 고객의 발주 축소 또는 결제 지연이 영업현금 유입에 미치는 영향을 고려한다.',
 'F11':'가격전가와 환헤지는 원가·환율 충격을 일부 완화하지만 적용 범위와 시차가 다르다. 잔여 노출은 마진과 현금흐름을 압박할 수 있으므로 두 비율을 합산하여 위험이 해소된 것으로 보지 않는다.',
 'F12':'미가동 설비는 추가 생산 여력을 제공하지만 고정비 부담도 수반한다. 실적 가동률과 계획·손익분기 가동률의 차이를 구분하고 수요 확보 여부에 따라 투자 회수 가능성을 판단한다.',
 'F13':'매출 증감은 외형 변화를 나타내며 수주잔고는 향후 매출의 보완 근거다. 수주의 취소·인도·수금 조건에 따라 현금 전환 시점이 달라질 수 있어 수주잔고를 즉시 상환재원으로 보지 않는다.',
 'F14':'영업이익은 이자와 원금 상환의 기초이나 실제 현금유입과 동일하지 않다. 매출 규모 및 비경상 항목과 구분하고 운전자본·설비투자 차감 후 현금흐름으로 상환재원을 연결한다.',
 'F15':'영업현금흐름은 실현된 현금 창출의 근거지만 그 전액을 원금 상환에 사용할 수 있는 것은 아니다. 유지보수 투자와 운전자본의 변동, 예정 만기를 함께 반영한다.',
 'F16':'차입금/EBITDA는 레버리지의 참고 지표이며 EBITDA 전액이 가용현금은 아니다. 차입 증가의 용도와 현금전환, 만기 구조에 따라 실제 상환부담을 평가한다.',
 'F17':'유동비율에는 재고와 채권이 포함되므로 즉시 가용현금과 구분한다. 현금의 사용제한 및 예정 현금유입과 원리금 지급 시점의 불일치가 단기 유동성 판단의 핵심이다.',
 'F18':'운전자본 증가는 매출 확대를 지원할 수 있으나 현금을 묶어 차입 수요를 늘릴 수도 있다. 회수기간·재고회전 및 연체·손상 정보를 확인하지 않고 자산의 질을 양호하다고 단정하지 않는다.',
 'F19':'표시된 손상·비경상비용은 해당 기간의 인식액이며 미래 손상 가능성의 부재를 의미하지 않는다. 비현금 손익은 영업현금흐름과 구분하여 반복 가능한 상환재원을 판단한다.',
 'F20':'계획 가동률·단가·생산량은 실적이 아니라 가정이다. 손익분기 여유가 수요나 단가 하락으로 축소되면 이익과 현금창출이 약화되므로 하방 민감도 및 잔여 공사비 조달을 함께 평가한다.',
 'F21':'단기차입 비중은 차환 노출의 근거다. 주주차입도 법적 후순위나 상환유예가 확인된 범위에서만 상환부담 완화 요인으로 인정한다.',
 'F22':'기말 현금과 과거 영업현금흐름을 단순 합산하여 향후 만기 대응이 확정된 것으로 보지 않는다. 원리금 지급 시점, 필수 투자, 가용 한도와 확약된 차환 여부에 따라 부족액을 판단한다.',
 'F23':'약정 여유와 이자보상 지표는 현재의 완충 정도를 보여준다. 변동금리 상승이나 EBITDA 감소가 여유를 축소할 수 있으며 미사용 한도와 실제 인출 가능성은 별도 확인 사항이다.',
 'F24':'이자보상 지표는 이자 지급의 참고 근거이며 원금상환 능력과 동일하지 않다. 실제 상환방식·만기 일정과 투자 후 가용현금의 대응이 확인된 범위에서만 취급 조건을 판단한다.',
 'F25':'담보는 채무불이행 시 회수보강 수단이며 정상 영업을 통한 상환능력을 대체하지 않는다. 보증의 제공자·수익자·금액·집행조건과 선순위 권리에 따라 실질 회수가능액이 달라진다.',
 'F26':'등급 명칭만으로 서로 다른 평가체계가 동일하다고 보지 않는다. 평가일·평가대상·전망을 확인하고 최근 실적과 현금흐름의 변화를 별도로 반영한다.',
 'F28':'조달합계와 소요자금의 일치는 산술적인 정합성이다. 자기자금 투입 시점과 대출 실행 조건, 실제 원금상환 일정이 확인되어야 현금흐름 적합성을 판단할 수 있다.',
 'F30':'공시 또는 입력된 이벤트 범위와 그 이후의 미확인 상황을 구분한다. 사업진척·인허가 확보가 매출과 수금의 실현을 보장하지 않으므로 잔여 자금소요와 영업현금 유입을 연결해 판단한다.'}

def dump(x): return json.dumps(x,ensure_ascii=False,separators=(',',':'))
def digest(x): return hashlib.sha256(x).hexdigest()
def sentences(s): return re.split(r'(?<=[.!?])\s+',s)

def repair_factor(row, audit, case):
    row=deepcopy(row); fid=row['input']['factor_id']; e=row['input']['evidence']; t=row['target']
    old=t['reasoning_summary']
    row['input']['reference_year']=2026
    row['input']['monetary_unit']='백만원 unless explicitly named otherwise'
    row['input']['synthetic_example']=True
    if fid=='F08':
        event=e.get('recent_event')
        event_text=(event or {}).get('description') if isinstance(event,dict) else event
        t['reasoning_summary']=(f"{e.get('industry','해당 산업')}의 원가와 전방수요 변화는 매출·마진에 영향을 미친다. "
           +(f"제공된 최근 상황은 {event_text}. " if event_text else '최근 업황 이벤트는 제공되지 않아 충격의 유무를 단정할 수 없다. ')
           +'원재료 수입에 따른 환율·조달 노출과 가격전가 가능성에 따라 현금흐름 영향을 판단한다.')
    elif fid in CAUSAL:
        prefix=' '.join(sentences(old)[:2 if fid in {'F03','F20'} else 1])
        # Do not preserve a categorical judgement embedded in the first sentence.
        prefix=re.sub(r'(상환여력은 유지되나|관리 가능한 수준|수용 가능|재무안정성 양호|현금창출력 우수|수익성 우수)','',prefix)
        t['reasoning_summary']=prefix+' '+CAUSAL[fid]
        t['strengths']=[]
        if fid in {'F03','F04','F05','F06','F07','F09','F10','F11','F12','F14','F18','F20','F26','F28','F30'}:
            t['judgement_level']='INFORMATIONAL'
    if fid=='F05':
        t['limitations']=list(dict.fromkeys(t.get('limitations',[])+['종속기업별 재무·보증·자금거래 미제공']))
    if fid=='F03':
        t['limitations']=list(dict.fromkeys(t.get('limitations',[])+['실제 지원약정 및 법적 보증 미제공']))
    metrics=checked_metrics(case)
    if fid=='F15':
        remaining=metrics['operating_cash_after_capex_2025']
        t['reasoning_summary']=sentences(old)[0]+f' 해당 기간 CAPEX 차감 후 현금은 {remaining:,}백만원이다. '+(
            '투자 후 현금 부족이 발생하여 현금보유액이나 추가 조달에 의존하며 원금상환 여력이 제약된다.' if remaining<0 else
            '투자 후 현금이 남지만 기초 현금, 필수 운전자본 및 만기 원리금과 지급 시점을 대조해야 실제 상환가능액을 판단할 수 있다.')
    if fid in {'F17','F22'}:
        gap=metrics['cash_only_maturity_gap']
        t['reasoning_summary']=sentences(old)[0]+(
            f' 기말 현금만으로 1년 내 만기를 충당할 경우 부족액은 {gap:,}백만원이다. 영업현금 유입과 확약된 차환을 검토하되 과거 현금흐름이 그대로 반복된다고 가정하지 않는다.' if gap>0 else
            '장부상 기말 현금은 1년 내 만기액을 커버한다. 다만 사용제한 현금과 필수 영업·투자 지출을 차감한 가용액 및 지급 시점을 기준으로 유동성 여유를 판단한다.')
    if fid=='F24':
        remaining=metrics['operating_cash_after_capex_2025']
        t['reasoning_summary']=sentences(old)[0]+(
            f' 해당 기간 CAPEX 차감 후 현금은 {remaining:,}백만원으로 투자 후 자체 현금이 부족하여 원금상환은 보유현금 또는 추가 조달에 의존한다. ' if remaining<0 else
            f' 해당 기간 CAPEX 차감 후 현금은 {remaining:,}백만원이며 이를 만기 원리금과 비교해야 한다. ')+CAUSAL[fid]
    if fid=='F29' and case['transaction']['loan_type'] in {'기한연장','리파이낸싱 자금'}:
        t['reasoning_summary']=('기존 익스포저와 신청금액의 단순 합산은 상환액을 차감하지 않은 가정이다. '
            f"본건은 {case['transaction']['loan_type']}으로, 기존 채무의 상환·대체 및 순증액이 미제공되어 거래 후 실제 익스포저는 확정할 수 없다. "
            '따라서 단순 합산액을 실제 신규 노출로 간주하여 한도 충족을 판단하지 않는다. 제공된 RAR 및 한도는 합성 정책값이며 실제 은행의 취급기준이 아니다.')
        t['strengths']=[]; t['concerns']=[]; t['limitations']=['상환·대체 금액 및 실제 순증액 미제공']
    if old!=t['reasoning_summary']:
        audit.append({'record_id':row['record_id'],'action':'repair_conditional_causal_summary','before':old,'after':t['reasoning_summary']})
    return row

def replace_text(obj, replacements):
    if isinstance(obj,str):
        for before,after in replacements: obj=obj.replace(before,after)
        return obj
    if isinstance(obj,list): return [replace_text(v,replacements) for v in obj]
    if isinstance(obj,dict): return {k:replace_text(v,replacements) for k,v in obj.items()}
    return obj

def numbers(obj):
    if isinstance(obj,bool) or obj is None: return []
    if isinstance(obj,(int,float)): return [float(obj)]
    if isinstance(obj,str):
        obj=re.sub(r'\b[A-Za-z][A-Za-z0-9_-]*\b','',obj)
        obj=re.sub(r'\d+차\b','',obj)
        return [float(v.replace(',','')) for v in re.findall(r'[-+]?\d[\d,]*(?:\.\d+)?',obj)]
    if isinstance(obj,list): return [n for v in obj for n in numbers(v)]
    if isinstance(obj,dict): return [n for k,v in obj.items() for n in numbers(str(k))+numbers(v)]
    return []

def unsupported_numbers(input_, target):
    allowed=set()
    for n in numbers(input_):
        for v in [n,n*100,n/100]:
            allowed.update(round(v,d) for d in (0,1,2,3,4))
    return sorted(set(n for n in numbers(target) if not any(abs(n-v)<=0.051 for v in allowed)))

def checked_metrics(case):
    f=case['financials']; d=case['debt']; b=case['business']; plan=case['project']['business_plan']
    def ratio(a,b,scale=1): return None if b in (0,None) or a is None else a/b*scale
    out={
      'revenue_growth_2025_pct':ratio(f['revenue']['2025']-f['revenue']['2024'],f['revenue']['2024'],100),
      'operating_margin_2025_pct':ratio(f['operating_profit']['2025'],f['revenue']['2025'],100),
      'debt_to_ebitda':ratio(f['total_borrowings']['2025'],f['ebitda']['2025']),
      'interest_coverage':ratio(f['ebitda']['2025'],f['interest_expense_2025']),
      'current_ratio_pct':ratio(f['current_assets_2025'],f['current_liabilities_2025'],100),
      'ocf_to_debt_pct':ratio(f['operating_cashflow']['2025'],f['total_borrowings']['2025'],100),
      'short_term_debt_share_pct':ratio(d['short_term_borrowings'],f['total_borrowings']['2025'],100),
      'maturity_cash_coverage':ratio(f['cash_2025'],d['debt_maturing_12m']),
      'net_working_capital_2025':f['receivables_2025']+f['inventory_2025']-f['payables_2025'],
      'age_years':2026-case['profile']['founded_year'],
      'operating_cash_after_capex_2025':f['operating_cashflow']['2025']-f['capex_2025'],
      'cash_only_maturity_gap':max(0,d['debt_maturing_12m']-f['cash_2025']),
      'maturity_horizon_years':1}
    return {k:round(v,4) if isinstance(v,float) else v for k,v in out.items()}

def contract(factors, case, task):
    context={'factors':{},'sources':{},'prior_findings':{},'datasets':{},'calculations':{},
             'reference_year':2026,'monetary_unit':'백만원','synthetic_example':True,
             'source_transaction':case['transaction']}
    findings=[]
    for row in factors:
        i=row['input']; fid=i['factor_id']; sid='S'+fid[1:]; t=row['target']
        context['factors'][fid]={'name':i['factor_name'],'required_evidence':[]}
        context['sources'][sid]={'content':i['evidence'],'missing':i.get('missing_evidence',[]),
                                 'conflicts':i.get('conflicts',[]),'reference_year':2026}
        findings.append({'factor_id':fid,'judgement':{
            'summary':t['reasoning_summary'],'evidence_ids':[sid] if i['evidence'] else [],
            'calculation_ids':['C1'] if fid in {'F01','F02','F13','F14','F15','F16','F17','F18','F21','F22','F23','F24'} else [],'risks':t.get('concerns',[]),'mitigants':t.get('strengths',[]),
            'missing':list(dict.fromkeys(i.get('missing_evidence',[])+t.get('limitations',[]))),
            'conflicts':i.get('conflicts',[]),'requirements':{}}})
    context['calculations']['C1']={'status':'EXECUTED','result':checked_metrics(case),
        'note':'Prepared by Python from the supplied synthetic case; not model-guessed calculations.'}
    return context, {'findings':findings,'requests':[]}

def markdown_section(t):
    parts=['## '+t['section_title']]+t.get('paragraphs',[])
    for table in t.get('tables',[]):
        cols=table.get('columns',[]); rows=table.get('rows',[])
        if cols:
            parts+=['단위: '+table.get('unit','원문 표 기준'),'| '+' | '.join(map(str,cols))+' |',
                    '| '+' | '.join(['---']*len(cols))+' |']
            parts+=['| '+' | '.join(map(str,r))+' |' for r in rows]
    return '\n\n'.join(parts)

def main():
    p=argparse.ArgumentParser(); p.add_argument('source',type=Path); p.add_argument('output',type=Path)
    a=p.parse_args(); raw=a.source.read_bytes(); assert digest(raw)==EXPECTED_SHA,'Unexpected source ZIP'
    a.output.mkdir(parents=True,exist_ok=True)
    z=zipfile.ZipFile(a.source); prefix='credit_lora_synthetic_v2_2/'
    def read(name):
        s=z.read(prefix+name).decode('utf-8')
        return [json.loads(l) for l in s.splitlines()] if name.endswith('.jsonl') else json.loads(s)
    splits=read('splits_by_archetype.json'); split_of={a:s for s,ids in splits.items() for a in ids}
    assert sum(map(len,splits.values()))==len(split_of),'Overlapping archetype splits'
    cases={x['case_id']:x for x in read('synthetic_cases.json')}; audit=[]; exclusions=[]; outputs=[]
    original_factors=read('factor_reasoning_sft.jsonl')
    repaired={x['record_id']:repair_factor(x,audit,cases[x['metadata']['case_id']]) for x in original_factors}
    by_case=defaultdict(dict)
    for r in repaired.values(): by_case[r['metadata']['case_id']][r['input']['factor_id']]=r
    replacements=defaultdict(list)
    for old in original_factors:
        new=repaired[old['record_id']]
        if old['target']['reasoning_summary']!=new['target']['reasoning_summary']:
            replacements[old['metadata']['case_id']].append((old['target']['reasoning_summary'],new['target']['reasoning_summary']))

    def emit(row, stage, context, answer, system):
        cid=row['metadata']['case_id']; archetype=row['metadata']['archetype_id']
        bad=unsupported_numbers(context,answer)
        if bad:
            exclusions.append({'record_id':row['record_id'],'reason':'unresolved_target_numbers','numbers':bad}); return
        outputs.append({'record_id':row['record_id'],'stage':stage,'split':split_of[archetype],
            'case_id':cid,'archetype_id':archetype,'messages':[{'role':'system','content':SYSTEM+system},
            {'role':'user','content':dump(context) if not isinstance(context,str) else context},
            {'role':'assistant','content':dump(answer) if not isinstance(answer,str) else answer}]})

    for row in repaired.values():
        cid=row['metadata']['case_id']; context,answer=contract([row],cases[cid],'factor')
        emit(row,'factor_style',context,answer,'각 factor_id마다 finding을 작성한다. 출력은 findings와 requests를 가진 압축 JSON이다.')
    for row in read('factor_bundle_reasoning_sft.jsonl'):
        cid=row['metadata']['case_id']; factors=[by_case[cid][fid] for fid in row['input']['factor_ids']]
        context,answer=contract(factors,cases[cid],'bundle')
        emit(row,'bundle',context,answer,'각 factor_id의 finding을 정확히 하나씩 작성한다. 공통 근거와 계산을 재사용하고 묶음 내 판단의 상충을 해소한다. 출력은 findings와 requests를 가진 압축 JSON이다.')
    for filename,stage in [('section_synthesis_sft.jsonl','section'),('full_report_sft.jsonl','full_report')]:
        for row in read(filename):
            row=deepcopy(row); cid=row['metadata']['case_id']; case=cases[cid]
            row=replace_text(row,replacements[cid]); context=row['input']
            context['reference_year']=2026; context['monetary_unit']='백만원'; context['synthetic_example']=True
            # Restore source facts for section tables, not the desired output or archetype label.
            context['source_financials']=case['financials']
            context['verified_calculations']=checked_metrics(case)
            context['source_business_plan']=case['project']['business_plan']
            context['source_sources_uses']=case['project']['sources_uses']
            context['source_transaction']=case['transaction']
            context['synthetic_policy']=case['internal_policy_synthetic']
            if stage=='section':
                for table in row['target'].get('tables',[]):
                    if table.get('table_type')=='business_plan_sensitivity':
                        base=case['project']['business_plan']['base_utilization']
                        downside=next((r[1] for r in table['rows'] if r[0]=='Downside'),None)
                        if downside is not None and abs(downside-(base-.15))<1e-8:
                            context['explicit_synthetic_scenario']={'downside_utilization':downside,
                                'change_percentage_points':-15,'note':'Explicit scenario assumption, not a forecast fact.'}
            for fj in context.get('factor_judgements',[]):
                if fj.get('factor_id') in by_case[cid]: fj.update(by_case[cid][fj['factor_id']]['target'])
            if stage=='full_report':
                # The original repeats the same opinions inside section_outputs.
                # Keep all 30 factor summaries, remove duplicate renderings/labels.
                context.pop('section_outputs',None)
                context.get('case_profile',{}).pop('company_label',None)
                context['factor_judgements']=[{k:v for k,v in fj.items() if k in
                    {'factor_id','reasoning_summary','limitations','concerns'}} for fj in context.get('factor_judgements',[])]
            if stage=='section':
                answer=markdown_section(row['target'])
                instruction='제공된 절의 근거와 요인별 판단을 통합하여 심사보고서 절을 한국어 Markdown으로 작성한다. 수치는 입력의 단위와 기간을 유지한다.'
            else:
                t=row['target']; answer='## 종합심사의견\n\n'+t['final_opinion']
                if t.get('required_followups'): answer+='\n\n취급 판단의 전제: '+'; '.join(t['required_followups'])
                if case['transaction']['loan_type'] in {'기한연장','리파이낸싱 자금'}:
                    answer+='\n\n'+by_case[cid]['F29']['target']['reasoning_summary']
                instruction='여러 요인과 절의 결과를 종합하여 종합심사의견을 한국어 Markdown으로 작성한다. 기존 결론을 복사하는 대신 상환재원과 위험·완화 요인, 취급 조건을 연결한다.'
            audit.append({'record_id':row['record_id'],'action':'restore_source_financials_and_propagate_factor_repairs'})
            emit(row,stage,context,answer,instruction)
    matches=defaultdict(list)
    for r in original_factors: matches[r['target']['reasoning_summary']].append(r)
    for style in read('style_rewrite_sft.jsonl'):
        matches_=matches.get(style['target'],[])
        if len(matches_)!=1:
            exclusions.append({'record_id':style['record_id'],'reason':'style_missing_or_ambiguous_source_case'}); continue
        source=matches_[0]; fixed=repaired[source['record_id']]
        row={'record_id':style['record_id'],'metadata':source['metadata']}
        context={'draft':style['input'],'evidence':fixed['input'],'verified_calculations':checked_metrics(cases[source['metadata']['case_id']])}
        emit(row,'factor_style',context,fixed['target']['reasoning_summary'],'초안의 문체를 간결하게 정리하되 추가된 사실 근거의 범위를 넘지 않는다. 출력은 완성된 심사의견 문단이다.')
        audit.append({'record_id':style['record_id'],'action':'attach_matched_evidence','source_record_id':source['record_id']})
    seen={}; unique=[]
    for row in outputs:
        key=digest(dump(row['messages']).encode())
        if key in seen:
            exclusions.append({'record_id':row['record_id'],'reason':'duplicate_messages','duplicate_of':seen[key]}); continue
        seen[key]=row['record_id']; unique.append(row)
    for split in splits:
        for stage in ['factor_style','bundle','section','full_report']:
            rows=[r for r in unique if r['split']==split and r['stage']==stage]
            (a.output/f'{stage}_{split}.jsonl').write_text(''.join(dump(r)+'\n' for r in rows),encoding='utf-8')
    (a.output/'repairs.jsonl').write_text(''.join(dump(r)+'\n' for r in audit),encoding='utf-8')
    (a.output/'exclusions.jsonl').write_text(''.join(dump(r)+'\n' for r in exclusions),encoding='utf-8')
    manifest={'source_sha256':digest(raw),'revision':'repair-v2-deduplicated-full-context','records':len(unique),
      'counts':dict(Counter(r['stage']+'_'+r['split'] for r in unique)),
      'repairs':len(audit),'exclusions':len(exclusions),'exclusion_reasons':dict(Counter(r['reason'] for r in exclusions)),
      'splits':splits,'dpo_used':False,'all30_in_training':False,
      'numeric_audit_limit':'Token/rounding membership is a filter, not proof of semantic numeric correctness.',
      'expert_quality_validated':False,
      'files':{p.name:digest(p.read_bytes()) for p in a.output.glob('*.jsonl')}}
    (a.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k not in {'files','splits'}},ensure_ascii=False))

if __name__=='__main__': main()
