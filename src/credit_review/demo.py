"""Deterministic synthetic fixture. Never presented as real LLM inference."""
import json
from datetime import date
from .models import Source


def demo_sources():
    return [Source(id="demo_cash", document_id="synthetic", page=1, published_at=date(2026, 3, 1),
        text="가상기업 TEST ONLY. 별도, 실제, 단위 백만원. 2025년 영업현금흐름 120, 현금 40, 1년 내 상환액 90. 신규여신 20, 2026년 말 일시상환.")]


class DemoClient:
    model = "SCRIPTED_DEMO_NOT_LLM"

    def next_action(self, context):
        state = context["state"]
        fid = context["factor"]["id"]
        if not state["evidence_ids"]:
            return json.dumps({"action": "search", "reason": "가상 자료 검색", "query": "영업현금흐름 현금 상환"}, ensure_ascii=False)
        if fid != "F24":
            return json.dumps({"action": "conclude", "reason": "데모는 F24만 분석", "judgement": {
                "summary": "이 요인은 가상 데모 범위 밖입니다.", "evidence_ids": [], "missing": context["factor"]["required_evidence"]}}, ensure_ascii=False)
        if not state["dataset_ids"]:
            row = {"period": "2025", "operating_cf": 120, "cash": 40, "maturing_debt": 90, "new_loan": 20}
            cols = [{"name": k, "dtype": "string" if k == "period" else "number",
                     "unit": None if k == "period" else "KRW_MILLION"} for k in row]
            return json.dumps({"action": "dataset", "reason": "근거에서 계산용 표 구성", "dataset": {
                "name": "repayment_inputs", "description": "가상 자료의 실제값. 예측이 아님.",
                "entity": "TEST_ONLY", "scope": "SEPARATE", "value_type": "ACTUAL", "columns": cols,
                "rows": [row], "cell_sources": [{k: ["demo_cash"] for k in row}], "period_column": "period"}}, ensure_ascii=False)
        if not state["calculation_ids"]:
            aid = state["dataset_ids"][-1]
            code = f"row = dfs[{aid!r}].iloc[0]\nresult = {{'historical_cf_to_maturity': float(row['operating_cf'] / row['maturing_debt']), 'cash_after_maturity': float(row['cash'] - row['maturing_debt'])}}"
            return json.dumps({"action": "calculate", "reason": "과거 CF 대비 만기도래액과 현금 부족액 계산", "calculation": {
                "purpose": "예측 아닌 과거 실적 기준 비교", "dataset_ids": [aid], "code": code,
                "assumptions": ["신규여신은 현금 유입으로 가산하지 않음", "향후 현금흐름을 보장하지 않음"]}}, ensure_ascii=False)
        return json.dumps({"action": "conclude", "reason": "계산 결과와 한계 정리", "judgement": {
            "summary": "가상 사례: 과거 영업CF는 만기도래액을 웃돌지만 보유현금만으로는 부족합니다. 향후 CF와 투자·운전자금 부담을 추가 확인해야 합니다.",
            "evidence_ids": ["demo_cash"], "calculation_ids": state["calculation_ids"],
            "risks": ["보유현금만으로 만기 상환 불가"], "mitigants": ["과거 영업현금 창출 실적"],
            "missing": ["향후 CF", "CAPEX", "운전자금 변동"],
            "requirements": {k: ["demo_cash"] for k in context["factor"]["required_evidence"]}}}, ensure_ascii=False)

    def synthesize(self, context):
        paragraphs = [{"text": f["state"]["judgement"]["summary"], "factor_ids": [fid],
            "evidence_ids": f["state"]["judgement"]["evidence_ids"],
            "calculation_ids": f["state"]["judgement"]["calculation_ids"]} for fid, f in context["factors"].items()]
        return json.dumps({"title": "가상 자료 하네스 데모 — 심사보고서 아님", "paragraphs": paragraphs,
                           "limitations": ["LLM 추론 대신 사전 정의된 JSON을 사용한 실행 검증"]}, ensure_ascii=False)
