"""Evaluation-only synthetic reasoning probes; never included in SFT files."""
import argparse
import json
from pathlib import Path

PROBES=[
 ('liquidity_gap','F24','상환재원 및 상환능력',
  '단위 백만원. 2025년 말 현금 120에는 사용제한 예금 20이 포함된다. 2026년 예상 영업현금흐름은 70, 현금 CAPEX는 40, 2026년 만기도래 원금은 200이다. 신규 확약한도나 주주지원약정은 없다.',
  {'available_cash':100,'forecast_ocf_after_capex':30,'cash_only_maturity_gap':70},
  ['현금 120에서 제한성 20을 제외한다.','현금 100+미래 OCF 70-CAPEX 40=130이며 원금 200 대비 부족 70이다.','차환 또는 추가 재원 없이는 전액 상환이 입증되지 않는다.']),
 ('support_not_cash','F03','주주 및 지배구조',
  '모회사가 차주 지분 80%를 보유하고 내부 주주지원여력 지수는 0.9다. 실제 자금지원 약정, 법적 지급보증, 지원시기와 금액은 제공되지 않았다. 차주는 3개월 후 70의 자금부족을 예상한다.',{},
  ['지분율과 지원여력을 지원의사·법적 의무와 구분한다.','지원금액을 만들어 부족분이 해소된다고 단정하지 않는다.']),
 ('repricing_not_maturity','F22','차입금 만기구조',
  '단위 백만원. 변동금리 대출 A 원금 300의 계약상 최종만기는 2030-12-31이며 이자율은 3개월마다 재설정된다. 별도 대출 B 원금 40은 2026-12-31 만기다. 심사일은 2026-01-01이고 원금 분할상환은 없다.',{},
  ['1년 내 원금 만기는 B의 40이다.','A의 3개월 재설정을 원금 만기로 해석하지 않는다.','A는 금리변동 위험과 장기만기 구조를 분리하여 설명한다.']),
 ('renewal_exposure','F29','당행 Exposure 및 수익성',
  '단위 백만원. 당행 기존 약정한도 100, 사용잔액 70이다. 신청은 동일 한도 100의 만기연장이며 한도 증액이나 추가 인출은 없다. 차주의 금융자산 신용위험 최대노출액은 900이다. 담보·신용환산율·수수료 정보는 없다.',{},
  ['단순 총한도는 갱신 후에도 100, 사용잔액은 70이다.','기존 100과 갱신 100을 더하지 않는다.','차주 금융자산 900을 당행 익스포저로 사용하지 않는다.','규제 EAD나 수익성을 임의 산출하지 않는다.']),
 ('nonrecurring_margin','F14','수익성',
  '단위 백만원. 2024년 매출 900, 영업이익 90. 2025년 매출 1000, 영업이익 100이며 2025년 영업이익에는 재고평가손실 환입 30이 포함되어 있다. 2024년에는 같은 환입이 없다. 다른 조정항목은 제공되지 않았다.',
  {'reported_margin_2024_pct':10,'reported_margin_2025_pct':10,'adjusted_2025_profit':70,'adjusted_2025_margin_pct':7},
  ['보고 영업이익은 증가하지만 보고 이익률은 10%로 같다.','환입 제거 시 2025년 이익 70, 이익률 7%다.','매출 증가만으로 본원적 수익성이 개선됐다고 단정하지 않는다.']),
 ('customer_concentration','F10','매출처 및 고객집중도',
  '단위 백만원. 매출 1000 중 고객 A 30%, B 25%, 나머지 합계 45%다. 나머지 고객 수와 개별 비중은 없다. A 매출의 매출총이익률은 20%이며 A 거래상실 시 다른 매출 대체나 고정비 절감 여부는 확인되지 않았다.',
  {'top_two_share_pct':55,'customer_a_revenue':300,'customer_a_gross_profit':60},
  ['상위 두 고객 55% 의존과 나머지 내역 미확인을 함께 고려한다.','기타 45%만으로 고객이 충분히 분산됐다고 단정하지 않는다.','A 거래상실의 매출총이익 영향 60을 회사 전체 순이익 감소와 동일시하지 않는다.'])
]


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('output',type=Path)
    args=parser.parse_args(); args.output.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    for name,factor,title,evidence,calculations,criteria in PROBES:
        payload={'factors':{factor:{'name':title}},'sources':{'S1':{'content':evidence}},
                 'calculations':{'C1':{'status':'EXECUTED','result':calculations}} if calculations else {},
                 'prior_findings':{},'synthetic_example':True}
        target={'findings':[{'factor_id':factor,'judgement':{'summary':' '.join(criteria)}}],'requests':[]}
        rows.append({'record_id':'probe-'+name,'stage':'factor_style','archetype_id':'evaluation-only',
          'evaluation_criteria':criteria,'train_allowed':False,'messages':[
            {'role':'system','content':'제공된 사실과 계산으로 기업여신 심사의견을 작성한다. 원인과 상환능력 영향을 연결하고 중요한 판단조건을 명시한다. 각 factor_id당 하나의 judgement(summary, evidence_ids, calculation_ids, risks, mitigants, missing)를 갖는 findings 배열과 requests 배열의 JSON으로 출력한다. 내부 사고 전문은 출력하지 않는다.'},
            {'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))},
            {'role':'assistant','content':json.dumps(target,ensure_ascii=False,separators=(',',':'))}]})
    args.output.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
    print('EVALUATION_ONLY_PROBES',len(rows))


if __name__=='__main__': main()
