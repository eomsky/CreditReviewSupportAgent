"""Prepare source-bound additions to report areas; preserve the accepted core."""
import argparse, copy, hashlib, json, time
from pathlib import Path
from section_prompt_router import route

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');ap.add_argument('--sections',nargs='+',required=True);ap.add_argument('--evidence');args=ap.parse_args()
    start=time.perf_counter();root=Path(__file__).resolve().parents[1];out=Path(args.output);out.mkdir(exist_ok=False)
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    save=lambda p,v:p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
    original=read(Path(args.input));body=original.get('report',original)
    selected=[s for s in body['sections'] if s['title'] in args.sections]
    assert len(selected)==len(set(args.sections))
    ids={sid for s in selected for p in s['paragraphs'] for sid in p.get('source_ids',[])}
    ids.update(sid for s in selected for t in s['tables'] for sid in t.get('source_ids',[]))
    sources=[s for s in body['sources'] if s['id'] in ids]
    if args.evidence:
        extra=read(Path(args.evidence));known={(s.get('document_id'),s.get('page'),s['text']) for s in body['sources']}
        for raw in extra['sources']:
            identity=(raw.get('document_id'),raw.get('page'),raw['text'])
            if identity in known:continue
            s=copy.deepcopy(raw);s['id']=f'S{len(body["sources"])+1}';body['sources'].append(s);sources.append(s);ids.add(s['id']);known.add(identity)
        save(out/'retrieval-audit.json',{'path':args.evidence,'elapsed_seconds':extra.get('elapsed_seconds'),'coverage':extra.get('coverage',[])})
    areas=copy.deepcopy(selected)
    for s in areas:
        for p in s['paragraphs']:p.pop('sources',None)
    baseline=root/'outputs/experiments/20260914/frozen/baseline_run/report-part-2/report.request.json'
    req=read(baseline);system,audit=route(req['messages'][0]['content'],'report')
    system+='\n이번 호출은 심사보고서의 추가 심층 분석 문단만 생성한다. 기존 문단/표는 별도로 보존하므로 다시 쓰지 않는다. 각 영역에 서로 다른 논점을 다루는 완결된 추가문단 2개를 작성한다. 단순 수치 재진술, 일반론, 같은 확인사항 반복은 제외. 원문에서 출처가 확인되는 사실→판단의 연결→실제 심사상 함의를 구체적으로 설명한다. 수치나 원인을 추정 사실로 만들지 않는다. 자료가 부족하면 정확히 어떤 근거가 어떤 판단에 필요한지 설명하되 모든 문단을 확인 필요 목록으로 대체하지 않는다. 기존 문단과 모순하거나 미확인 사항을 확인된 것처럼 서술하지 않는다. 각 문단 contribution은 기존 내용에 더한 분석을 짧게 기재하는 검토 메타이며 화면에 표시하지 않는다. 표 및 종합의견은 수정하지 않는다.\n특히 별도/연결, 비교기간, 단위, 주석 범위를 구분한다. 불특정다수 매출→고객 이탈위험 낮음, 관계사 거래→효율성 개선, 공란/0→시장지위 낮음 등의 근거없는 추론 금지. 관계사 손익은 중첩합산 금지. 차입/출자 지원 의무는 실제 약정이 있어야 단정. 조건부 시나리오는 명시적 가정이며 원문 실적과 분리한다.'
    titles=[s['title'] for s in selected]
    paragraph={'type':'object','properties':{'text':{'type':'string','minLength':150,'maxLength':1000},'contribution':{'type':'string'},'source_ids':{'type':'array','minItems':1,'items':{'type':'string','enum':list(ids)}}},'required':['text','contribution','source_ids'],'additionalProperties':False}
    schema={'type':'object','properties':{'sections':{'type':'array','minItems':len(titles),'maxItems':len(titles),'items':{'type':'object','properties':{'title':{'type':'string','enum':titles},'paragraphs':{'type':'array','minItems':2,'maxItems':2,'items':paragraph}},'required':['title','paragraphs'],'additionalProperties':False}}},'required':['sections'],'additionalProperties':False}
    focus={
        '업체개요':'법인/연결 범위 변화, 지배구조와 실제 지원 의무, 관계사 손익 범위. 순이익/자본/부채비율 일반 설명은 다른 영역이므로 제외.',
        '사업성':'제품/서비스별 매출 동인, 거래처·매입처 구성과 계약/회수 구조, 업종별 수익 발생 방식. 재무비율/차입 증가 설명 제외.',
        '수익성':'영업→세전→순손익 원인, 비현금/반복성 여부와 현금 이자 부담. 출처 없는 원인 단정 금지.',
        '재무안정':'차입 만기와 가용 유동성, 자본변동, 충당금·회수 위험.',
        '상환능력':'자금 사용·조달과 상환 일정, 기초현금 포함 실제/계획/가정의 구분.',
        '채권보전':'권리·순위·통화·보증 방향과 실제 집행 가능성, 지원 의향과 의무 구분.',
        '종합 심사의견':'개별 위험과 보완 요소를 종합해 상환에 영향을 주는 조건과 우선 확인 사항 도출.'}
    outline=[{'title':s['title'],'paragraphs':[p['text'] for p in s['paragraphs']]} for s in body['sections']]
    req['messages']=[{'role':'system','content':system},{'role':'user','content':json.dumps({'existing_sections':areas,'whole_report_for_duplicate_check':outline,'area_focus':{t:focus.get(t,t) for t in titles},'sources':sources,'depth_requirements':(root/'docs/REPORT_DEPTH_REQUIREMENTS.md').read_text(encoding='utf-8'),'reference_methodology':(root/'docs/REPORT_CASE_REFERENCE_REVIEW.md').read_text(encoding='utf-8').split('## 공통 설계에 반영할 사항')[1]},ensure_ascii=False)}]
    req['structured_outputs']={'json':schema};req['temperature']=0.1
    save(out/'generation.request.json',req);save(out/'source-artifact.json',original);save(out/'prompt-adaptation-audit.json',audit)
    save(out/'review-contract.json',{'step':19,'target_seconds':50,'sections':titles,'initial_preparation_seconds':time.perf_counter()-start,'input_sha256':hashlib.sha256(Path(args.input).read_bytes()).hexdigest(),'scope':'additional depth generation, not entire report or total step19'})
    print('prepared',titles,len(sources),'sources')

if __name__=='__main__':main()
