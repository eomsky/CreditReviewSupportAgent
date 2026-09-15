"""Scope the frozen multi-section instruction catalogue, never source evidence."""
HEADERS={
 'financial_accounts':'가. 재무제표 주요계정(현황 및 향후전망)',
 'profitability':'나. 수익성(현황 및 향후전망)',
 'financial_stability':'다. 재무안정성 및 자산의 질(현황 및 향후전망)',
 'cashflow_repayment':'라. 현금흐름 및 채무상환능력(현황 및 향후전망)',
 'customer_concentration':'마. 주요 매출처 및 매출비중 변동 추이',
 'summary_2':'종합의견2 — 조사자 종합의견',
}

def scope(text,key):
    if key not in HEADERS:return text
    markers=['\n'+x+'\n' for x in HEADERS.values()]+['\n심사보고서 작성 지침\n']
    positions=[text.find(x) for x in markers]
    # Unrecognized/custom catalogue: leave the prompt intact.
    if any(x<0 for x in positions) or positions!=sorted(set(positions)):return text
    index=list(HEADERS).index(key)
    return text[:positions[0]]+text[positions[index]:positions[index+1]]+text[positions[-1]:]
