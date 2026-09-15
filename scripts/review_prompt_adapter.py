"""Translate generation-only field contracts into the review response contract.
Every changed line is retained in the audit; unknown instructions stay verbatim.
"""
import hashlib

def adapt(prompt):
    rules=[
        ('응답 필수 구조: paragraphs에는', '검토 대상 초안의 핵심 특이사항과 상세 분석의견을 모두 검토한다. 특이사항만 검토하면 불완전하다. 논점별 문단과 실제 원문 source_ids를 보존하며 필요한 수정만 revisions로 반환한다.'),
        ('leverage의 capital_change_evidence_quote가 null이면', 'causal_basis.capital_change.decision이 insufficient_evidence이면 자본 감소의 원인을 순손실 발생으로 확정하지 않는다. 두 관측을 구분하고 자본변동 상세 확인 한계를 보존한다. 부채/자본 양측의 비율변화 분석을 생략하지 않는다.'),
        ('상세 analysis_paragraphs를 먼저 작성하고', '상세 분석과 핵심 특이사항의 일관성을 검토한다. 요약에 상세 근거로 확인하지 못한 원인이나 담보평가 판단을 추가하지 않는다. 자산 대비 차입비율은 장부상 비율이며 담보 여력 변화로 대체하지 않는다.'),
        ('analysis_paragraphs는 네 논점별 문단 객체다.', '기존 논점별 상세 문단과 특이사항을 보존한다. 필수 논점과 근거 수치를 빠뜨리지 않고 문단 간 중복만 피한다. 적자 전환 원인을 다루는 경우 세전·법인세 영향을 정확히 보존한다.'),
    ]
    changes=[];result=[]
    for number,line in enumerate(prompt.splitlines(),1):
        replacement=next((value for prefix,value in rules if line.startswith(prefix)),line)
        if replacement!=line:changes.append({'line':number,'before':line,'after':replacement,'reason':'generation schema contract mapped to review schema; quality obligation retained'})
        result.append(replacement)
    output='\n'.join(result)
    return output,{'input_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'output_sha256':hashlib.sha256(output.encode()).hexdigest(),'changes':changes,'unchanged_lines':len(result)-len(changes),'quality_equivalence':'requires semantic result comparison; not proven by textual mapping'}
