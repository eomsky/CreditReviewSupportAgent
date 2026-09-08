"""Evidence-first review with eight dependency-aware calls for seven report sections."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from time import monotonic
from pydantic import Field
from .models import Model, Dataset, DatasetCalculation, Judgement, Action
from .registry import FACTORS
from .evidence_queries import QUERIES, NUMERIC_FACTORS
from .table_access import prompt_source, table_card
from .parallel import Measurements
from .store import atomic_json
from .report_plan import REPORT_SECTION_CALLS


# Independent source reviews run together.  Risk and repayment then receive the
# completed business/finance findings, and the final section receives every
# earlier conclusion.  This preserves report coherence while reducing wall time.
SECTION_WAVES = (("01", "02", "03", "05a", "05b"), ("04", "06"), ("07",))

NUMERIC_INPUTS = ['F13','F14','F15','F16','F17','F18','F21','F22']
DISCOVERY = {
    'F02':['회사의 연혁','설립 인적분할'],
    'F05':['연결대상 종속회사 개황','종속기업 재무정보'],
    'F10':['주요 매출처 매출 비중','고객 집중도 매출액'],
    'F13':['연결 포괄손익계산서 매출액 영업이익'],
    'F14':['연결 포괄손익계산서 매출액 영업이익'],
    'F16':['연결 재무상태표 부채총계 자본총계'],
    'F17':['연결 재무상태표 현금및현금성자산'],
    'F15':['연결 현금흐름표 영업활동'],
    'F20':['향후 투자 계획','수주상황 수주잔고'],
    'F22':['유동성위험 계약상 잔존만기','금융부채 만기분석'],
    'F24':['연결 현금흐름표 영업활동','차입금 계약상 만기'],
    'F30':['입찰참가자격 제한 집행정지','제재현황 과징금 소송'],
}


class PreparedDataset(Model):
    dataset: Dataset
    after_dataset: DatasetCalculation | None = None


class Foundation(Model):
    datasets: list[PreparedDataset] = Field(default_factory=list, max_length=1)
    limitations: list[str] = Field(default_factory=list)


class Finding(Model):
    factor_id: str
    judgement: Judgement


class EvidenceRequest(Model):
    factor_ids: list[str]
    question: str
    query: str = ''
    source_ids: list[str] = Field(default_factory=list)


class BundleReview(Model):
    findings: list[Finding]
    requests: list[EvidenceRequest] = Field(default_factory=list, max_length=3)


def record_part_timing(h, call_id, title, status, started, ended, run_started):
    """Persist actual worker occupancy, excluding time spent waiting in the pool."""
    path = h.store.path / "section_timings.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"parts": {}}
    current["parts"][call_id] = {
        "title": title,
        "status": status,
        "started_seconds": round(max(0, started - run_started), 3),
        "ended_seconds": round(max(0, ended - run_started), 3),
        "duration_seconds": round(max(0, ended - started), 3),
    }
    atomic_json(path, current)


def part_timings(h):
    path = h.store.path / "section_timings.json"
    if not path.exists():
        return []
    parts = json.loads(path.read_text(encoding="utf-8")).get("parts", {})
    order = [section["call_id"] for section in REPORT_SECTION_CALLS] + ["09"]
    return [{"call_id": key, **parts[key]} for key in order if key in parts]


def evidence_pack(h, ids, extra=None, budget=42000, prefer_consolidated=False, only_extra=False):
    """Deduplicate ranked bodies once, preserving exact IDs and omitted markers."""
    ranked, by_factor = {}, {}
    for fid in ids:
        hits = h.retriever.search(QUERIES.get(fid, FACTORS[fid]['name']), limit=10)
        candidates = [hit['source'] for hit in hits]
        selected = candidates[:3]
        for query in DISCOVERY.get(fid,[]):
            discovered=[hit['source'] for hit in h.retriever.search(query,limit=8)]
            if fid in NUMERIC_INPUTS:
                discovered=[s for s in discovered if table_card(s)][:2]
            else:
                discovered=discovered[:2]
            selected = discovered + selected
        if fid in NUMERIC_FACTORS:
            selected = [s for s in candidates if table_card(s)][:2] + selected
        by_factor[fid] = list(dict.fromkeys(s['id'] for s in selected))
        for pos,s in enumerate(selected):
            if s['id'] not in ranked:
                ranked[s['id']] = [s, 0.0]
            ranked[s['id']][1] += 1/(pos+1)
    for s in extra or []:
        ranked[s['id']] = [s, 100]
    if only_extra:
        allowed={s['id'] for s in extra or []}
        ranked={sid:row for sid,row in ranked.items() if sid in allowed}
    from .evidence_scope import explicit_scope
    has_consolidated=prefer_consolidated and any(explicit_scope(row[0])['scope']=='CONSOLIDATED' for row in ranked.values())
    if has_consolidated:
        for entry in ranked.values():
            card=table_card(entry[0])
            section=' '.join(str(x) for x in (card or {}).get('section_path',[]))
            if card and explicit_scope(entry[0])['scope']=='CONSOLIDATED' and any(
                title in section for title in ('연결 재무상태표','연결 포괄손익계산서','연결 현금흐름표')):
                entry[1]+=100  # Primary statements precede incidental note matches.
    excluded_scopes=('SEPARATE','CONFLICT') if has_consolidated else ('CONFLICT',) if prefer_consolidated else ()
    packed, used = {}, 0
    for row, score in sorted(ranked.values(), key=lambda v:-v[1]):
        source = prompt_source(row, loaded=True)
        if source.get('financial_scope',{}).get('scope') in excluded_scopes:
            continue
        # Loaded Markdown already contains row/column labels. Keep scope and
        # provenance but do not send a second structural copy of every label.
        card = source.get('table_index')
        if card:
            for table in card['tables']:
                table.pop('rows', None)
                table.pop('columns', None)
        size = len(json.dumps(source, ensure_ascii=False))
        if used+size > budget:
            continue  # Never label a truncated body as fully read.
        packed[row['id']] = source
        used += size
    # All common evidence is delivered to every member. Availability is not truth.
    for fid in ids:
        f = h.state.factors[fid]
        f.evidence_ids = sorted(set(f.evidence_ids) | set(packed))
        f.read_source_ids = sorted(set(f.read_source_ids) | set(packed))
    return {'review_date':str(h.state.review_date), 'sources':packed,
            'factor_source_ids':{fid:[sid for sid in sids if sid in packed] for fid,sids in by_factor.items()},
            'omitted_source_ids':[sid for sid in ranked if sid not in packed]}


def foundation_context(h,ids):
    """Use complete primary statements when their structural headings exist."""
    from .evidence_scope import explicit_scope
    titles=('연결재무상태표','연결포괄손익계산서','연결현금흐름표')
    primary=[]; found=set()
    for source in h.retriever.sources.values():
        if source.kind!='table': continue
        path=source.metadata.get('structured',{}).get('section_path',[])
        section=''.join(str(x).replace(' ','') for x in path)
        matched={title for title in titles if title in section}
        if matched:
            row=source.model_dump(mode='json')
            if explicit_scope(row)['scope']=='CONSOLIDATED':
                primary.append(row); found.update(matched)
    if len(found)>=2:
        return evidence_pack(h,ids,extra=primary,budget=32000,prefer_consolidated=True,only_extra=True)
    return evidence_pack(h,ids,budget=32000,prefer_consolidated=True)


def review_context(h, ids, extra=None, evidence_budget=42000):
    context = evidence_pack(h, ids, extra, budget=evidence_budget,
                            prefer_consolidated=bool(set(ids)&set(NUMERIC_INPUTS)))
    context['factors'] = {fid:FACTORS[fid] for fid in ids}
    from .review_criteria import CRITERIA
    context['review_criteria']={fid:CRITERIA[fid] for fid in ids if fid in CRITERIA}
    datasets = {aid for f in h.state.factors.values() for aid in f.dataset_ids}
    calculations = {aid for f in h.state.factors.values() for aid in f.calculation_ids}
    context['datasets'] = {aid:h.store.get(aid)['payload'] for aid in datasets}
    context['calculations'] = {aid:h.store.get(aid)['payload'] for aid in calculations
                               if h.store.get(aid)['payload'].get('status') == 'EXECUTED'}
    for fid in ids:
        f=h.state.factors[fid]
        f.dataset_ids=sorted(set(f.dataset_ids)|datasets)
        f.calculation_ids=sorted(set(f.calculation_ids)|set(context['calculations']))
        refs={sid for data in context['datasets'].values() for row in data['cell_sources'] for source_ids in row.values() for sid in source_ids}
        f.evidence_ids=sorted(set(f.evidence_ids)|refs)
    # A later section only needs the earlier conclusions for cross-section
    # consistency.  Sending the complete judgement objects (requirements,
    # source lists, missing items, and conflicts) made the finance section grow
    # with every preceding section and exceed the model context window.  Keep a
    # compact analytical bridge so every one-pass section receives enough room
    # for its own evidence.
    context['prior_findings']={
        fid: {
            'summary': f.judgement.summary,
            'risks': f.judgement.risks,
            'mitigants': f.judgement.mitigants,
        }
        for fid,f in h.state.factors.items() if f.judgement
    }
    context['foundation_errors']=getattr(h,'foundation_errors',[])
    return context


def analyse_prepared(h, targets, concurrency=2, metrics=None, time_budget=900, **kwargs):
    """Build seven report sections in eight one-pass dependency-aware LLM calls.

    Retrieval and projection are local. A section attempt marker is written before
    the call, so a resume continues with the next untouched section instead of
    re-inferring a failed or completed section.
    """
    metrics = metrics or Measurements()
    deadline = metrics.started + time_budget
    h.client.set_deadline(deadline)
    target_set = set(targets)

    def event(kind, fid=None, value=None, active=()):
        return {
            'kind': kind, 'factor_id': fid, 'value': value, 'active': list(active),
            'finished': sum(bool(h.state.factors[f].judgement) for f in targets),
            'total': len(targets), 'metrics': metrics.snapshot(),
        }

    by_call = {section['call_id']: section for section in REPORT_SECTION_CALLS}
    slots = max(1, min(2, int(concurrency)))
    with ThreadPoolExecutor(max_workers=slots, thread_name_prefix='credit-section') as pool:
        for wave_call_ids in SECTION_WAVES:
            jobs = []
            for call_id in wave_call_ids:
                section = by_call[call_id]
                ids = [fid for fid in section['factor_ids'] if fid in target_set]
                if not ids:
                    continue
                marker = h.store.path / f"section_{call_id}_attempt.json"
                # Completed, failed, and submitted markers all prevent re-inference.
                if marker.exists() or all(h.state.factors[fid].judgement or h.state.factors[fid].error for fid in ids):
                    continue
                if monotonic() >= deadline:
                    raise TimeoutError('Section review reached its analysis deadline')

                # Context construction remains on the single writer.  Members of a
                # wave share the same completed prior waves, never partial peer state.
                # Each finance half receives its own evidence budget.  Across
                # both calls the available evidence remains comparable with the
                # former single bundle, while either request stays below the
                # 32K model context window.
                context = review_context(h, ids, evidence_budget=22000 if call_id in ('05a','05b') else 42000)
                context.update({
                    'single_pass': True,
                    'report_section': {
                        'number': section['number'], 'title': section['title'],
                        'call_id': call_id, 'call_title': section['call_title'],
                        'blocks': list(section['blocks']),
                    },
                })
                parent = h.store.put(f"section_{call_id}_input", context)
                atomic_json(marker, {
                    'status': 'SUBMITTED', 'section': section['call_title'],
                    'factor_ids': ids, 'input_artifact_id': parent,
                })
                jobs.append((section, ids, marker, parent, context))
                for fid in ids:
                    yield event('status', fid, {
                        'action': 'review',
                        'question': f"{section['number']}. {section['call_title']} 목차 작성",
                    }, ids)
            h.save()

            def timed_review(context, timing):
                timing['started'] = monotonic()
                try:
                    return h.client.review_bundle(context)
                finally:
                    timing['ended'] = monotonic()

            futures = {}
            for section, ids, marker, parent, context in jobs:
                timing = {}
                futures[pool.submit(timed_review, context, timing)] = (section, ids, marker, parent, timing)
            for future in as_completed(futures):
                section, ids, marker, parent, timing = futures[future]
                part_status = 'FAILED'
                try:
                    raw = future.result()
                    output = h.store.put(f"section_{section['call_id']}_output", {'raw': raw}, [parent])
                    reply = BundleReview.model_validate_json(raw)
                    seen = set()
                    for finding in reply.findings:
                        fid = finding.factor_id
                        if fid not in ids or fid in seen:
                            raise ValueError('Duplicate or unexpected factor in section response')
                        seen.add(fid)
                        try:
                            h.apply(fid, Action(action='conclude', reason='Single-pass section judgement',
                                                judgement=finding.judgement), output)
                            h.state.factors[fid].error = None
                            h.state.factors[fid].steps += 1
                            if metrics.first_report_seconds is None:
                                metrics.first_report_seconds = monotonic() - metrics.started
                            yield event('state', fid, h.state.factors[fid].model_copy(deep=True), ids)
                        except ValueError as error:
                            h.state.factors[fid].error = str(error)
                            h.store.event(action='section_validation', factor_id=fid, error=str(error))
                    missing = set(ids) - seen
                    for fid in missing:
                        h.state.factors[fid].error = 'Section response omitted this factor'
                    atomic_json(marker, {
                        'status': 'COMPLETED' if not missing else 'PARTIAL',
                        'section': section['call_title'], 'factor_ids': ids,
                        'accepted_factor_ids': sorted(seen - missing), 'output_artifact_id': output,
                    })
                    part_status = 'COMPLETED' if not missing else 'PARTIAL'
                except Exception as error:
                    h.store.event(action='section_failure', stage=section['call_title'], factors=ids, error=str(error))
                    for fid in ids:
                        if not h.state.factors[fid].judgement:
                            h.state.factors[fid].error = str(error)[:1000]
                    atomic_json(marker, {
                        'status': 'FAILED', 'section': section['call_title'],
                        'factor_ids': ids, 'error': str(error)[:1000],
                    })
                finally:
                    record_part_timing(h, section['call_id'], section['call_title'], part_status,
                                       timing.get('started', monotonic()), timing.get('ended', monotonic()), metrics.started)
                    h.save()
                    atomic_json(h.store.path/'performance.json', metrics.snapshot())
                    for fid in ids:
                        yield event('done', fid, active=ids)

    h.save()
    atomic_json(h.store.path/'performance.json', metrics.snapshot())
