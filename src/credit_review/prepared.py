"""Evidence-first review: shared numeric preparation, then substantive bundles.

Retrieval is local. The LLM authors data and Python plans; isolated Python executes
them before numerical interpretation. Independent bundles occupy other GPU slots.
"""
import json
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from time import monotonic
from pydantic import Field
from .models import Model, Dataset, DatasetCalculation, Judgement, Action
from .registry import FACTORS
from .evidence_queries import QUERIES, NUMERIC_FACTORS
from .table_access import prompt_source, table_card
from .parallel import Measurements
from .store import atomic_json

BUNDLES = [list(FACTORS)[:5], list(FACTORS)[5:12], list(FACTORS)[12:20],
           list(FACTORS)[20:26], list(FACTORS)[26:29], ['F30']]
NUMERIC_INPUTS = ['F13','F14','F15','F16','F17','F18','F21','F22']
DISCOVERY = {
    'F02':['회사의 연혁','설립 인적분할'],
    'F05':['연결대상 종속회사 개황','종속기업 재무정보'],
    'F10':['주요 매출처 매출 비중','고객 집중도 매출액'],
    'F22':['유동성위험 계약상 잔존만기','금융부채 만기분석'],
    'F24':['연결 현금흐름표 영업활동','차입금 계약상 만기'],
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


def evidence_pack(h, ids, extra=None, budget=42000):
    """Deduplicate ranked bodies once, preserving exact IDs and omitted markers."""
    ranked, by_factor = {}, {}
    for fid in ids:
        hits = h.retriever.search(QUERIES.get(fid, FACTORS[fid]['name']), limit=10)
        candidates = [hit['source'] for hit in hits]
        selected = candidates[:3]
        for query in DISCOVERY.get(fid,[]):
            selected = [hit['source'] for hit in h.retriever.search(query,limit=2)] + selected
        if fid in NUMERIC_FACTORS:
            selected = [s for s in candidates if table_card(s)][:2] + selected
        by_factor[fid] = list(dict.fromkeys(s['id'] for s in selected))
        for pos,s in enumerate(selected):
            if s['id'] not in ranked:
                ranked[s['id']] = [s, 0.0]
            ranked[s['id']][1] += 1/(pos+1)
    for s in extra or []:
        ranked[s['id']] = [s, 100]
    packed, used = {}, 0
    for row, score in sorted(ranked.values(), key=lambda v:-v[1]):
        source = prompt_source(row, loaded=True)
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


def review_context(h, ids, extra=None):
    context = evidence_pack(h, ids, extra)
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
    context['prior_findings']={fid:f.judgement.model_dump() for fid,f in h.state.factors.items() if f.judgement}
    context['foundation_errors']=getattr(h,'foundation_errors',[])
    return context


def analyse_prepared(h, targets, concurrency=2, metrics=None, time_budget=100, **kwargs):
    """At most one evidence follow-up per bundle; no factor routing round trips."""
    metrics=metrics or Measurements()
    deadline=metrics.started+time_budget
    h.client.set_deadline(deadline)
    jobs={}
    followups=[]
    foundation_done=False
    review_done=False
    bundles=[list(f for f in ids if f in targets and not h.state.factors[f].judgement) for ids in BUNDLES]
    pending=[ids for ids in bundles if ids]
    pool=ThreadPoolExecutor(max_workers=max(1,min(2,concurrency)),thread_name_prefix='credit-prepared')

    def event(kind, fid=None, value=None):
        return {'kind':kind,'factor_id':fid,'value':value,'active':[f for job in jobs.values() for f in job['ids']],
            'finished':sum(bool(h.state.factors[f].judgement) for f in targets),'total':len(targets),'metrics':metrics.snapshot()}

    def submit(kind, ids, extra=None, final=False):
        context=evidence_pack(h,ids,budget=32000) if kind=='foundation' else review_context(h,ids,extra)
        if kind!='foundation':
            context['final_pass']=final
            context['review_pass']=kind=='quality'
        parent=h.store.put('prepared_'+kind+'_input',context)
        future=pool.submit(getattr(h.client,'prepare_financial' if kind=='foundation' else 'review_bundle'),context)
        jobs[future]={'kind':kind,'ids':ids,'context':context,'parent':parent,'final':final}
        h.save()

    try:
        submit('foundation',[f for f in NUMERIC_INPUTS if f in targets])
        while pending or jobs or followups or not review_done:
            if monotonic()>=deadline: raise TimeoutError('Prepared review reached its analysis deadline')
            while len(jobs)<min(2,max(1,concurrency)):
                ready=next((ids for ids in pending if (foundation_done or not set(ids)&set(NUMERIC_INPUTS))
                    and (ids!=['F30'] or (not jobs and not followups and len(pending)==1))),None)
                if ready:
                    pending.remove(ready)
                    submit('bundle',ready)
                    for fid in ready:
                        yield event('status',fid,{'action':'review','question':FACTORS[fid]['name']+'의 근거·반대 근거와 상환능력 영향을 판단'})
                elif foundation_done and followups and (not pending or pending==[['F30']]):
                    ids,extra=followups.pop(0)
                    submit('bundle',ids,extra,final=True)
                elif not pending and not jobs and not followups and not review_done:
                    review_done=True
                    ids=[f for f in ['F02','F05','F17','F20','F22','F24','F29']
                         if f in targets and h.state.factors[f].judgement]
                    if ids and deadline-monotonic()>15:
                        submit('quality',ids,final=True)
                        for fid in ids:
                            yield event('status',fid,{'action':'review','question':FACTORS[fid]['name']+'의 수치 범위와 판단 근거를 교차 검토'})
                else: break
            if not jobs: break
            completed,_=wait(jobs,timeout=.3,return_when=FIRST_COMPLETED)
            if not completed:
                yield event('heartbeat')
                continue
            for future in completed:
                job=jobs.pop(future)
                try:
                    raw=future.result()
                    output=h.store.put('prepared_'+job['kind']+'_output',{'raw':raw},[job['parent']])
                    if job['kind']=='foundation':
                        data=json.loads(raw)
                        h.foundation_errors=[]
                        for raw_item in data.get('datasets',[]):
                            try:
                                item=PreparedDataset.model_validate(raw_item)
                                h.apply('F13',Action(action='dataset',reason='Shared financial preparation',
                                    dataset=item.dataset,after_dataset=item.after_dataset),output)
                            except Exception as error:
                                h.foundation_errors.append(str(error)[:800])
                                h.store.event(action='foundation_validation',error=str(error))
                        h.store.put('foundation_limitations',{'limitations':data.get('limitations',[]),
                            'errors':h.foundation_errors},[output])
                    else:
                        reply=BundleReview.model_validate_json(raw)
                        seen=set()
                        for finding in reply.findings:
                            fid=finding.factor_id
                            if fid not in job['ids'] or fid in seen: raise ValueError('Duplicate or unexpected bundle factor')
                            seen.add(fid)
                            try:
                                h.apply(fid,Action(action='conclude',reason='Evidence-based bundle judgement',judgement=finding.judgement),output)
                                h.state.factors[fid].error=None
                                h.state.factors[fid].steps+=1
                                if metrics.first_report_seconds is None: metrics.first_report_seconds=monotonic()-metrics.started
                                yield event('state',fid,h.state.factors[fid].model_copy(deep=True))
                            except ValueError as error:
                                h.state.factors[fid].error=str(error)
                                h.store.event(action='bundle_validation',factor_id=fid,error=str(error))
                        if reply.requests and not job['final']:
                            extra=[]
                            for req in reply.requests:
                                if not set(req.factor_ids).issubset(job['ids']): continue
                                if req.query:
                                    extra.extend(hit['source'] for hit in h.retriever.search(req.query,limit=3))
                                if req.source_ids:
                                    try: extra.extend(h.retriever.read(req.source_ids))
                                    except ValueError: pass
                            if extra: followups.append((job['ids'],extra))
                except Exception as error:
                    h.store.event(action='prepared_failure',stage=job['kind'],factors=job['ids'],error=str(error))
                    for fid in job['ids']:
                        h.state.factors[fid].error=str(error)[:1000]
                    from .run_health import service_failure
                    if service_failure(error):
                        raise  # An unavailable shared server cannot serve later bundles.
                finally:
                    if job['kind']=='foundation': foundation_done=True
                    h.save()
                    atomic_json(h.store.path/'performance.json',metrics.snapshot())
                    for fid in job['ids']: yield event('done',fid)
    finally:
        pool.shutdown(wait=False,cancel_futures=True)
        h.save()
        atomic_json(h.store.path/'performance.json',metrics.snapshot())
