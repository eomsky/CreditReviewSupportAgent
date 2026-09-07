"""Train-only, source-grounded rehearsal; original validation/test stay unchanged.

Reduce irrelevant common metrics and replace checklist-like summaries for key
cash/forecast/collateral factors with conditional, case-specific conclusions.
Reference reports and evaluation probes are never read here.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from prepare_data import unsupported_numbers
from tokenize_data import BASE, REVISION, STAGES, stratified, encode_record

CALCS={
 'F01':['age_years'],'F02':['age_years'],'F13':['revenue_growth_2025_pct'],
 'F14':['operating_margin_2025_pct'],
 'F15':['operating_cash_after_capex_2025','ocf_to_debt_pct'],
 'F16':['debt_to_ebitda'],
 'F17':['current_ratio_pct','maturity_cash_coverage','cash_only_maturity_gap','maturity_horizon_years'],
 'F18':['net_working_capital_2025'],
 'F21':['short_term_debt_share_pct'],
 'F22':['cash_only_maturity_gap','maturity_horizon_years'],
 'F23':['interest_coverage'],
 'F24':['operating_cash_after_capex_2025','cash_only_maturity_gap','maturity_cash_coverage',
        'interest_coverage','debt_to_ebitda','maturity_horizon_years']}


def compact(value): return json.dumps(value,ensure_ascii=False,separators=(',',':'))
def number(value): return f'{value:,.2f}'.rstrip('0').rstrip('.')


def revise(finding,source,metrics):
    fid=finding['factor_id']; judgment=finding['judgement']; text=None
    if fid=='F15':
        ocf=source['operating_cashflow']['2025']; net=metrics['operating_cash_after_capex_2025']
        text=(f'2025년 영업현금흐름은 {number(ocf)}백만원이며 CAPEX 차감 후 현금은 {number(net)}백만원이다. '
             +('투자지출이 영업현금 유입을 초과하여 해당 기간 투자 후 내부상환재원이 부족했다. ' if net<0 else
               '투자지출 후에도 현금이 남았으나 그 금액을 초과하는 원금 만기는 차환이나 별도 재원이 필요하다. ')
             +'이는 과거 실적이므로 같은 현금이 향후에도 유입된다고 확정하지 않는다.')
    elif fid in {'F17','F22'}:
        gap=metrics['cash_only_maturity_gap']; cash=source['cash_2025']
        text=f'기말 현금 {number(cash)}백만원을 향후 1년 내 원금 만기와 비교하면 현금만으로 충당하지 못하는 금액은 {number(gap)}백만원이다. '
        text+=('현금을 전부 사용할 수 있다고 보아도 부족분이 남으므로 차환 또는 추가 현금유입에 의존한다. ' if gap>0 else
               '표시 현금은 비교 대상 원금 만기를 산술적으로 충당하지만 사용제한과 지급시점은 반영되지 않았다. ')
        text+='재고·매출채권을 포함한 유동자산이나 과거 영업현금흐름을 현재 가용현금에 더해 상환이 확보된 것으로 보지 않는다.'
    elif fid=='F24':
        net=metrics['operating_cash_after_capex_2025']; gap=metrics['cash_only_maturity_gap']
        coverage=source['interest_coverage']
        text=(f'제시된 EBITDA/이자비용은 {number(coverage)}배이나, 투자 후 과거 영업현금은 {number(net)}백만원이고 '
              f'기말 현금 대비 1년 내 원금 만기 부족액은 {number(gap)}백만원이다. ')
        if net<0: text+='투자 후 현금이 마이너스여서 과거 이익지표만으로 내부 상환재원이 충분하다고 판단할 수 없다. '
        elif gap>0: text+='투자 후 현금창출은 상환에 보탬이 되지만 과거 실적이며, 만기 부족분의 확약된 조달재원이 입증되지는 않았다. '
        else: text+='현금의 산술적 여유는 보완 요인이지만 사용제한 및 실제 지급일별 원리금 대응은 별도이다. '
        text+=('본건 상환방식이 제공되지 않아 원금과 이자의 시점별 대응 및 무조건적인 취급 적정성은 판단할 수 없다.'
               if source.get('repayment_method') is None else
               f"본건은 {source['repayment_method']} 구조이므로 해당 지급일별 원금·이자와 미래 가용현금이 대응한다는 조건에서 취급 가능성을 판단한다.")
    elif fid=='F20':
        plan=source['business_plan']
        text=(f"계획 매출은 {number(source['base_plan_sales'])}백만원, 제시된 하방 매출은 {number(source['downside_plan_sales'])}백만원이다. "
              f"계획 가동률 {number(plan['base_utilization']*100)}%와 손익분기 가동률 {number(plan['break_even_utilization']*100)}% 사이의 "
              f"여유는 {number(source['break_even_headroom_pct'])}%p이다. ")
        text+=('계획 자체가 손익분기점에 못 미치므로 계획 매출만으로 영업손익 개선을 전제할 수 없다. '
               if source['break_even_headroom_pct']<0 else
               '가동률 하락이 이 여유를 소진하면 손익분기점을 밑돌 수 있어 계획 이익의 실현은 수요 확보에 좌우된다. ')
        text+='계획·하방 수치는 실적이나 확정 수금이 아니며 잔여 투자비와 원리금 일정을 반영한 현금 검증이 필요하다.'
    elif fid=='F25':
        text=(f"담보커버리지 {number(source['collateral_coverage_ratio'])}배와 보증/자기자본 {number(source['guarantee_to_equity_ratio'])}배가 제시되어 있다. ")
        text+=('입력자료상 주요 소송은 없으나, ' if source.get('major_litigation') is False else
               '입력자료상 주요 소송이 있어 잠재 현금유출을 검토해야 하며, ' if source.get('major_litigation') is True else
               '주요 소송 여부가 제공되지 않았으며, ')
        text+='비율만으로 선순위 공제 후 회수액이나 보증의 방향·법적 의무가 확인되지는 않는다. '
        text+='따라서 이를 본건 원리금 전액의 회수보강으로 인정할 근거는 부족하고, 정상 상환은 별도의 영업현금과 만기 대응에 의존한다.'
    if text is not None:
        judgment['summary']=text
    # A favorable event is not a risk merely because it is an event.
    if fid=='F02':
        event=source.get('recent_event') or {}
        description=event.get('description','') if isinstance(event,dict) else str(event)
        if '고정금리' in description and ('전환' in description or '비중 확대' in description):
            judgment['risks']=[x for x in judgment.get('risks',[]) if x!=description]
    return finding


def prepare(data,output,counts):
    output.mkdir(parents=True,exist_ok=True)
    maps={}; audit=[]; factor_rows=[]
    original=[json.loads(s) for s in (data/'factor_style_train.jsonl').read_text(encoding='utf-8').splitlines()]
    for source_row in original:
        row=deepcopy(source_row); target=row['messages'][-1]['content']
        if not target.startswith('{'): continue
        context=json.loads(row['messages'][-2]['content']); reply=json.loads(target)
        metrics=context.get('calculations',{}).get('C1',{}).get('result',{})
        for finding in reply['findings']:
            fid=finding['factor_id']; sid='S'+fid[1:]
            old=finding['judgement']['summary']
            revise(finding,context['sources'][sid]['content'],metrics)
            maps[(row['case_id'],fid)]={'old':old,'new':finding['judgement']['summary']}
        keep={key for f in reply['findings'] for key in CALCS.get(f['factor_id'],[])}
        relevant={k:v for k,v in metrics.items() if k in keep}
        if relevant: context['calculations']['C1']['result']=relevant
        else:
            context['calculations']={}
            for finding in reply['findings']: finding['judgement']['calculation_ids']=[]
        row['messages'][-2]['content']=compact(context); row['messages'][-1]['content']=compact(reply)
        audit.append({'record_id':row['record_id'],'input_chars_before':len(source_row['messages'][-2]['content']),
                      'input_chars_after':len(row['messages'][-2]['content']),'retained_calculations':sorted(relevant)})
        factor_rows.append(row)
    # Rehearse all four output tasks together, propagating the same revised
    # factor summaries into bundle/section/full-report train inputs and targets.
    all_rows={'factor_style':factor_rows}
    for stage in STAGES[1:]:
        rows=[]
        for line in (data/f'{stage}_train.jsonl').read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            for (case,fid),edit in maps.items():
                if case!=row['case_id'] or edit['old']==edit['new']: continue
                for message in row['messages']:
                    message['content']=message['content'].replace(edit['old'],edit['new'])
            if stage=='bundle':
                context=json.loads(row['messages'][-2]['content'])
                reply=json.loads(row['messages'][-1]['content'])
                metrics=context['calculations']['C1']['result']
                for finding in reply['findings']:
                    revise(finding,context['sources']['S'+finding['factor_id'][1:]]['content'],metrics)
                keep={key for f in reply['findings'] for key in CALCS.get(f['factor_id'],[])}
                context['calculations']['C1']['result']={k:v for k,v in metrics.items() if k in keep}
                if not keep:
                    context['calculations']={}
                    for finding in reply['findings']: finding['judgement']['calculation_ids']=[]
                row['messages'][-2]['content']=compact(context); row['messages'][-1]['content']=compact(reply)
            rows.append(row)
        all_rows[stage]=rows
    selected=[]; rejected=[]
    for stage,count in zip(STAGES,counts):
        candidates=[]
        for row in all_rows[stage]:
            flags=unsupported_numbers(row['messages'][:-1],row['messages'][-1]['content'])
            if flags: rejected.append({'record_id':row['record_id'],'numeric_flags':flags})
            else: candidates.append(row)
        selected.extend(stratified(candidates,count,83))
    # Interleave output tasks, then Trainer applies its deterministic shuffle.
    selected.sort(key=lambda r:hashlib.sha256(r['record_id'].encode()).hexdigest())
    source_path=output/'refinement_source_train.jsonl'
    source_path.write_text(''.join(compact(r)+'\n' for r in selected),encoding='utf-8')
    (output/'refinement_audit.json').write_text(json.dumps({'edits':audit,'rejected':rejected},ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'source_manifest_sha256':hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),
              'revision':'train-only-mixed-refinement-v3','counts':dict(Counter(r['stage'] for r in selected)),
              'validation_test_modified':False,'probes_or_reference_reports_used':False,
              'raw_training_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),
              'numeric_rejections':len(rejected),'expert_quality_validated':False}
    (output/'refinement_manifest.json').write_text(json.dumps(manifest,indent=2))
    return selected,manifest


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('data',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('--counts',default='320,160,80,32'); parser.add_argument('--tokenize',action='store_true')
    args=parser.parse_args(); rows,manifest=prepare(args.data,args.output,list(map(int,args.counts.split(','))))
    if args.tokenize:
        from transformers import AutoTokenizer
        tokenizer=AutoTokenizer.from_pretrained(BASE,revision=REVISION,local_files_only=True)
        validation=[]
        for stage in STAGES:
            raw=[json.loads(s) for s in (args.data/f'{stage}_validation.jsonl').read_text().splitlines()]
            validation.extend(stratified(raw,3,97))
        token_counts={}
        for split,source in [('train',rows),('validation',validation)]:
            encoded=[]
            for row in source:
                item,error=encode_record(tokenizer,row,6144)
                if error: raise ValueError('Refinement exceeds token budget: '+row['record_id'])
                encoded.append(item)
            path=args.output/f'refinement_{split}.jsonl'
            path.write_text(''.join(compact(r)+'\n' for r in encoded))
            token_counts[split]={'records':len(encoded),'tokens':sum(len(r['input_ids']) for r in encoded),
                                 'max_tokens':max(len(r['input_ids']) for r in encoded)}
        (args.output/'tokenization_manifest.json').write_text(json.dumps({**manifest,'base_model':BASE,
            'revision':REVISION,'counts':token_counts,'truncation':False},indent=2))
        print('TOKENIZED',json.dumps(token_counts),flush=True)
    print('REFINEMENT',json.dumps(manifest),flush=True)


if __name__=='__main__': main()
