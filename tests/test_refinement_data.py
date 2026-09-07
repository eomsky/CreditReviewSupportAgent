import importlib.util
from pathlib import Path
import sys

root=Path(__file__).parents[1]/'training/credit_lora'
sys.path.insert(0,str(root))
try:
    spec=importlib.util.spec_from_file_location('refinement',root/'prepare_refinement.py')
    refinement=importlib.util.module_from_spec(spec); spec.loader.exec_module(refinement)
finally:
    sys.path.pop(0)


def test_cash_deficit_is_a_conditional_conclusion_not_future_cash():
    finding={'factor_id':'F24','judgement':{'summary':'old'}}
    source={'interest_coverage':8.5,'repayment_method':None}
    metrics={'operating_cash_after_capex_2025':-240,'cash_only_maturity_gap':700}
    result=refinement.revise(finding,source,metrics)['judgement']['summary']
    assert '-240백만원' in result and '700백만원' in result
    assert '과거' in result and '상환방식이 제공되지 않아' in result
    assert '충분하다고 판단할 수 없다' in result


def test_no_major_litigation_is_preserved_without_promising_recovery():
    finding={'factor_id':'F25','judgement':{'summary':'old'}}
    source={'collateral_coverage_ratio':.51,'guarantee_to_equity_ratio':.17,'major_litigation':False}
    result=refinement.revise(finding,source,{})['judgement']['summary']
    assert '0.51배' in result and '0.17배' in result
    assert '입력자료상 주요 소송은 없으나' in result
    assert '원리금 전액의 회수보강으로 인정할 근거는 부족' in result
    assert 'LTV' not in result
