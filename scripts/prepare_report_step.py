"""Prepare a report candidate from frozen instructions and accepted opinions."""
import copy
import hashlib
import json
from pathlib import Path
from accepted_evidence_bundle import build
from evidence_columnar import compact

ROOT = Path(__file__).resolve().parents[1]
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
save = lambda p, d: p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')

def main():
    out = ROOT/'outputs/step_trials/C20.30-step13-input'
    out.mkdir(exist_ok=False)
    parent = ROOT/'outputs/step_trials/C20.29.1-step12-r1'
    gate = read(parent/'step-result.json')
    if not gate.get('allow_step13') or gate['quality_status'] != 'pass':
        raise ValueError('Step12 must pass first')
    for name, digest in gate['artifact_sha256'].items():
        assert hashlib.sha256((parent/name).read_bytes()).hexdigest() == digest
    baseline = ROOT/'outputs/experiments/20260914/frozen/baseline_run/report-part-1'
    request = read(baseline/'report.request.json')
    payload = json.loads(request['messages'][1]['content'])
    frozen_drafts = payload.pop('prior_model_drafts')
    save(out/'replaced-frozen-drafts.json', frozen_drafts)
    sources, sections, lineage = build(ROOT, payload['sources'], runs=[
        'C20.27.1.1s-step10-replay', 'C20.29.1-step12-r1'])
    payload['prior_model_drafts'] = dict(zip(['customer_concentration','summary_2'], sections))
    payload['accepted_context_rules'] = (
        'prior_model_drafts는 검토된 해석이며 원문은 sources이다. 준비요약도 원문을 대체하지 않는다. '
        '원문 표의 0을 실제 시장점유율이나 자료없음으로 임의 해석하지 않는다. '
        '전기 매출처 상세와 합계가 불일치하므로 합계를 매출처 상세로 복사하지 않는다. '
        '별도 안내표시를 추가하지 않는다. 불확실성은 필요한 분석에만 반영한다. '
        '현재 목차는 업체개요와 사업성이다. 재무상환 상세는 뒤 목차와 중복하지 않는다. '
        '__evidence_records_v1__은 원문 JSON의 columns/rows 무손실 표현이다.')
    save(out/'original-source-archive.json', sources)
    encoding = []
    for source in sources:
        original = source['text']
        source['text'], changed = compact(original)
        encoding.append({'source_id':source['id'], 'original_sha256':hashlib.sha256(original.encode()).hexdigest(),
                         'original_chars':len(original), 'encoded_chars':len(source['text']), 'lossless':True})
    payload['sources'] = sources
    def aliases(node):
        if isinstance(node, dict):
            enum = node.get('enum')
            if enum and all(isinstance(x,str) and x.startswith('S') and x[1:].isdigit() for x in enum):
                node['enum'] = [s['id'] for s in sources]
            for value in node.values(): aliases(value)
        elif isinstance(node, list):
            for value in node: aliases(value)
    aliases(request['structured_outputs']['json'])
    request['messages'][1]['content'] = json.dumps(payload, ensure_ascii=False)
    save(out/'generation.request.json', request)
    save(out/'preparation.json', read(baseline/'report.preparation.json'))
    save(out/'lineage.json', lineage)
    save(out/'source-encoding-audit.json', encoding)
    save(out/'preparation-audit.json', {
        'step':13, 'version':'C20.30', 'status':'prepared_not_executed',
        'frozen_system_prompt_verbatim': request['messages'][0] == read(baseline/'report.request.json')['messages'][0],
        'replaced_obsolete_drafts':True, 'source_count':len(sources),
        'input_token_preflight_required':True, 'quality_status':'unassessed', 'end_to_end':False})
    print(out)

if __name__ == '__main__': main()
