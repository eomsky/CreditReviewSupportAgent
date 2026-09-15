"""Separate accounting levels, asset quality and collateral support in review."""
import ast

RULE='causal_claims의 추가 항목을 원문으로 먼저 판단하고 문장 수정에 반영한다. asset_quality_evidence가 ratios_only이면 잔액·비중·회전율만으로 부실 위험이 낮다거나 회수 가능성이 높다고 확정하지 않는다. 효율·비중의 관측과 연령·연체·충당금·체화 정보의 확인 한계를 구별한다. collateral_realization_evidence가 book_values_only이면 장부자산/차입금은 자산 대비 차입 부담만 보여주며 담보 여력 판단에는 평가액·선순위·설정·처분제약 근거가 추가로 필요하다. earnings_bridge_and_changes에서는 영업외손익의 당기 수준과 전기 대비 증감액을 구분하고, 세전손익·법인세·순손익 연결을 확인한다. 금융비용 증가와 순손실이 함께 나타났다는 이유만으로 직접 인과로 바꾸지 않는다. 자본총계 감소를 자본잠식과 동일시하지 않는다. 자본잠식 또는 그 위험의 현실화를 주장하려면 납입자본 대비 자본총계와 손실 누적·전망의 근거를 확인하며, 단기 순손실만으로 확정하지 않는다. 원문 지표의 평균/기말/누적 정의를 본문에서 유지하고 비중을 절대규모로 바꾸어 해석하지 않는다. 이러한 근거 제한을 remaining_gaps에만 숨기지 말고 해당 본문의 과도한 단정도 수정한다.'


def patch(source):
    marker="    checks=obj({category:copy.deepcopy(check) for category in categories})"
    assert source.count(marker)==1
    source=source.replace(marker,marker+'''
    causal=checks['properties']['causal_claims']
    causal['properties']['reason']['maxLength']=160
    causal['properties']['asset_quality_evidence']={'type':'string','enum':['direct_asset_quality_details','ratios_only','not_applicable']}
    causal['properties']['collateral_realization_evidence']={'type':'string','enum':['valuation_and_prior_claims','book_values_only','not_applicable']}
    causal['properties']['earnings_bridge_and_changes']={'type':'string','maxLength':200,'description':'손익 수준과 증감 구분 및 세전·법인세·순손익 대응. 관련 없으면 해당없음.'}
    causal['required']+=['asset_quality_evidence','collateral_realization_evidence','earnings_bridge_and_changes']
''')
    marker="    system=with_reasoning(system)"
    assert source.count(marker)==1
    source=source.replace(marker,"    system+='\\n'+"+repr(RULE)+"\n"+marker)
    ast.parse(source)
    return source
