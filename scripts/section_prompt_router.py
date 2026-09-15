"""Route explicit template sections, retaining all shared instructions verbatim."""
import hashlib
HEADINGS={
 'financial_accounts':'가. 재무제표 주요계정(현황 및 향후전망)',
 'profitability':'나. 수익성(현황 및 향후전망)',
 'financial_stability':'다. 재무안정성 및 자산의 질(현황 및 향후전망)',
 'cash_flow':'라. 현금흐름 및 채무상환능력(현황 및 향후전망)',
 'customers':'마. 주요 매출처 및 매출비중 변동 추이',
 'summary2':'종합의견2 — 조사자 종합의견',
}
def route(prompt,key):
    if key not in HEADINGS and key != 'report':raise ValueError('Unregistered prompt route')
    lines=prompt.splitlines();starts=[]
    for name,heading in HEADINGS.items():
        positions=[i for i,line in enumerate(lines) if line.strip()==heading]
        if not positions:raise ValueError('Missing explicit template boundary: '+name)
        starts.append((positions[0],name))
    starts.sort()
    end=next((i for i,line in enumerate(lines) if line.strip()=='심사보고서 작성 지침'),None)
    if end is None or end<=starts[-1][0]:raise ValueError('Missing shared suffix boundary')
    assignments=['shared']*len(lines)
    for n,(start,name) in enumerate(starts):
        stop=starts[n+1][0] if n+1<len(starts) else end
        assignments[start:stop]=[name]*(stop-start)
    selected=[line for line,owner in zip(lines,assignments) if owner in ('shared',key)]
    audit={'selected_route':key,'source_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
           'requirements':[{'line':i+1,'owner':owner,'text':line,'included':owner in ('shared',key)} for i,(line,owner) in enumerate(zip(lines,assignments))],
           'quality_status':'not validated; section and end-to-end comparisons required'}
    return '\n'.join(selected),audit
