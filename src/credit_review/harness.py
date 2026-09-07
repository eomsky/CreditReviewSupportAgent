from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from pathlib import Path

from .calculations import DockerExecutor, validate_dataset
from .models import Action, Dataset, FactorState, ReviewState
from .registry import FACTORS
from .evidence_queries import QUERIES, NUMERIC_FACTORS
from .table_access import prompt_source, table_card
from .retrieval import Retriever
from .store import Store, atomic_json, json_text


class Harness:
    def __init__(self, store: Store, state: ReviewState, retriever: Retriever, client, executor=None):
        self.store, self.state, self.retriever, self.client = store, state, retriever, client
        self.executor = executor or DockerExecutor()

    @classmethod
    def create(cls, root, case_id, review_date, sources, client, mode="LIVE", embedding_model="", executor=None):
        revision = hashlib.sha256(json_text([s.model_dump(mode="json") for s in sources]).encode()).hexdigest()
        run_id = "run_" + uuid.uuid4().hex
        state = ReviewState(case_id=case_id, run_id=run_id, review_date=review_date, mode=mode,
            source_revision=revision, factors={fid: FactorState(factor_id=fid) for fid in FACTORS})
        store = Store(root, case_id, run_id)
        store.put("sources", {"sources": [s.model_dump(mode="json") for s in sources]})
        store.put("manifest", {"source_revision": revision, "review_date": str(review_date), "mode": mode,
            "factor_registry": FACTORS, "embedding_model": embedding_model,
            "llm_model": getattr(client, "model", "scripted-demo"), "harness_version": "0.1.0"})
        harness = cls(store, state, Retriever(sources, review_date, embedding_model), client, executor)
        harness.save()
        return harness

    def save(self):
        active = [f for f in self.state.factors.values() if f.applicability != "NOT_APPLICABLE"]
        self.state.generation_status = "DRAFT_ALLOWED" if any(f.judgement for f in active) else "BLOCKED"
        # Final publication requires a later human/semantic verification stage.
        atomic_json(self.store.path / "state.json", self.state.model_dump(mode="json"))

    def context(self, fid):
        factor = self.state.factors[fid]
        focused = (factor.recent_source_ids or factor.evidence_ids)[-6:]
        rows = self.retriever.read(focused)
        # Avoid repeating full parent pages beside each paragraph/table. Parents remain readable by ID.
        loaded = {sid for f in self.state.factors.values() for sid in f.read_source_ids}
        sources = [prompt_source(row, row['id'] in loaded) for row in rows if row['id'] in focused]
        # Bound the source window without deleting the underlying source artifacts.
        # Mark excerpts explicitly so their absence cannot be interpreted as evidence.
        for source in sources:
            if not source.get('read_complete') and len(source['text']) > 6500:
                source['text'] = source['text'][:6500]
                source['excerpt_only'] = True
                source['omission_note'] = 'Excerpt only; search a focused child passage before using omitted table rows or notes.'
        return {"factor": FACTORS[fid], "state": {**factor.model_dump(mode="json", exclude={"failed_response"}),
                    "failed_response": factor.failed_response[:2000] if factor.failed_response else None},
                "review_date": str(self.state.review_date), "mode": self.state.mode,
                "sources": sources,
                "source_window": "Only focused evidence is shown. Use read for earlier evidence_ids or parent_id; all IDs remain preserved.",
                "retrieval_guidance": ("Repeated retrieval returned the same evidence window. Reframe the question to search again, or conclude with supported limitations."
                    if factor.retrieval_stalls >= 2 else "Search or read when it adds relevant evidence."),
                "datasets": {aid: self.store.get(aid)["payload"] for aid in factor.dataset_ids},
                "calculations": {aid: self.store.get(aid)["payload"] for aid in factor.calculation_ids},
                "related_findings": {k: v.judgement.model_dump(mode="json") for k, v in self.state.factors.items() if k != fid and v.judgement},
                "shared_datasets": {aid: {k: v for k, v in self.store.get(aid)["payload"].items() if k not in ("rows", "cell_sources")}
                    for other in self.state.factors.values() for aid in other.dataset_ids if aid not in factor.dataset_ids},
                "available_actions": (["plan"] if not factor.inquiry else (["reframe"] if factor.reframes < 3 else []))
                    + (["search", "read"] if factor.retrieval_stalls < 2 else (["read"] if any(s.get("read_required") for s in sources) else [])) + ["conclude"]
                    + (["dataset", "calculate", "reuse"] if fid not in {'F01','F02','F03','F04','F05','F06','F07','F08','F09','F25','F26','F27'} or factor.reframes else [])}

    def prepare_evidence(self, fid):
        """Offer initial candidates without spending an LLM round trip on routing.

        Candidates are not verified facts: the model still plans, reads, reframes,
        calculates and validates conclusions through the normal harness.
        """
        factor = self.state.factors[fid]
        if factor.steps or factor.evidence_ids or factor.judgement:
            return
        query = QUERIES.get(fid, FACTORS[fid]['name'])
        parent = self.store.put('evidence_prefetch', {'factor_id': fid, 'query': query})
        self.apply(fid, Action(action='search', query=query, reason='Initial evidence candidates'), parent)
        focused = list(factor.recent_source_ids)
        # Loading a known needed table is local retrieval, not an LLM routing turn.
        # Keep all other candidates discoverable and require source/semantic checks.
        if fid in NUMERIC_FACTORS:
            table = next((row['id'] for row in self.retriever.read(focused[:2])
                          if row['id'] in focused[:2] and table_card(row)), None)
            if table:
                self.apply(fid, Action(action='read', source_ids=[table],
                    reason='Numeric factor needs the top matched table segment'), parent)
                factor.recent_source_ids = [table] + [sid for sid in focused if sid != table]
        factor.retrieval_stalls = 0
        self.save()

    def step(self, fid: str, max_steps: int = 15, repair_attempts: int = 0, on_status=None):
        factor = self.state.factors[fid]
        if factor.judgement or factor.status in ("LIMIT_REACHED", "NO_PROGRESS"):
            return factor
        if factor.steps >= max_steps:
            factor.status = "LIMIT_REACHED"
            self.save()
            return factor
        # Single-writer lease protects against double clicks / concurrent browser sessions.
        lock = self.store.path / getattr(self, "lock_name", ".step.lock")
        with lock.open("x"):
            pass
        request_id = None
        raw = None
        try:
            factor.steps += 1
            context = self.context(fid)
            request_id = self.store.put("llm_input", context, factor.dataset_ids + factor.calculation_ids)
            raw = self.client.next_action(context)
            response_id = self.store.put("llm_output", {"raw": raw}, [request_id])
            action = Action.model_validate_json(raw)
            if on_status:
                question = action.inquiry.question if action.inquiry else (factor.inquiry.question if factor.inquiry else FACTORS[fid]["name"])
                if action.action == "reframe":
                    question += " — " + action.inquiry.change_reason
                on_status(action.action, question)
            signature = hashlib.sha256(action.model_dump_json(exclude={"reason"}).encode()).hexdigest()
            factor.repeated_actions = factor.repeated_actions + 1 if signature == factor.last_signature else 0
            factor.last_signature = signature
            if factor.repeated_actions >= 2:
                factor.status = "NO_PROGRESS"
                return factor
            result = self.apply(fid, action, response_id)
            factor.error = None
            factor.failed_response = None
            factor.consecutive_errors = 0
            self.store.event(factor_id=fid, action=action.action, request_id=request_id, output_id=result)
        except Exception as error:
            factor.error = f"{type(error).__name__}: {error}"
            factor.failed_response = raw[:12000] if raw else None
            factor.consecutive_errors += 1
            factor.status = "RETRYING" if isinstance(error, ValueError) and factor.consecutive_errors <= repair_attempts else "ERROR"
            self.store.event(factor_id=fid, status="ERROR", error=factor.error, request_id=request_id)
        finally:
            lock.unlink(missing_ok=True)
            self.save()
        return factor

    def apply(self, fid, action: Action, parent_id: str):
        f = self.state.factors[fid]
        f.status = "IN_PROGRESS"
        if action.action in ("plan", "reframe"):
            if action.action == "plan" and f.inquiry:
                raise ValueError("A plan exists; use reframe to change the question")
            if action.action == "reframe":
                if f.reframes >= 3:
                    raise ValueError("Reframe limit reached; conclude with supported qualifications")
                f.reframes += 1
            previous = f.inquiry.model_dump() if f.inquiry else None
            f.inquiry = action.inquiry
            f.retrieval_stalls = 0
            f.report_text = None
            self.state.report_id = None
            return self.store.put("inquiry", {"previous": previous, "current": f.inquiry.model_dump(),
                "factor_id": fid}, [parent_id])
        if action.action in ("search", "read"):
            old_window = set(f.recent_source_ids)
            if action.action == "search":
                hits = self.retriever.search(action.query)
                rows = [h["source"] for h in hits]
                payload = {"query": action.query, "hits": hits}
            else:
                rows = self.retriever.read(action.source_ids)
                f.read_source_ids = sorted(set(f.read_source_ids) | set(action.source_ids))
                payload = {"sources": rows}
            f.recent_source_ids = [s["id"] for s in rows if s["id"] in action.source_ids] if action.action == "read" else [s["id"] for s in rows]
            f.retrieval_stalls = f.retrieval_stalls + 1 if set(f.recent_source_ids) == old_window else 0
            f.evidence_ids = sorted(set(f.evidence_ids) | {s["id"] for s in rows})
            return self.store.put(action.action, payload, [parent_id])
        if action.action == "reuse":
            available = {aid for other in self.state.factors.values() for aid in other.dataset_ids}
            if not set(action.reuse_dataset_ids).issubset(available):
                raise ValueError("Reuse requires a dataset from this run's source revision")
            for aid in action.reuse_dataset_ids:
                data = Dataset.model_validate(self.store.get(aid)["payload"])
                refs = {sid for row in data.cell_sources for ids in row.values() for sid in ids}
                self.retriever.read(sorted(refs))
                validate_dataset(data, refs)
                f.evidence_ids = sorted(set(f.evidence_ids) | refs)
                if aid not in f.dataset_ids:
                    f.dataset_ids.append(aid)
            return self.store.put("reuse", {"dataset_ids": action.reuse_dataset_ids}, [parent_id] + action.reuse_dataset_ids)
        if action.action == "dataset":
            data = action.dataset
            refs = {sid for row in data.cell_sources for ids in row.values() for sid in ids}
            self.require_table_read(refs)
            df = validate_dataset(data, set(f.evidence_ids))
            aid = self.store.put("dataset", data.model_dump(mode="json"), [parent_id])
            path = self.store.path / "datasets"
            path.mkdir(exist_ok=True)
            df.to_json(path / f"{aid}.json", orient="table", force_ascii=False)
            f.dataset_ids.append(aid)
            f.status = "CALCULABLE"
            return aid
        if action.action == "calculate":
            plan = action.calculation
            if not set(plan.dataset_ids).issubset(f.dataset_ids):
                raise ValueError("Calculation must reference this factor's available datasets")
            datasets = {aid: self.store.get(aid)["payload"] for aid in plan.dataset_ids}
            for data in datasets.values():
                validate_dataset(Dataset.model_validate(data), set(f.evidence_ids))
            request = self.store.put("calculation_request", plan.model_dump(), [parent_id] + plan.dataset_ids)
            output = self.executor.execute(plan, datasets)
            aid = self.store.put("calculation", {"plan": plan.model_dump(), **output}, [request])
            f.calculation_ids.append(aid)
            return aid
        judgement = action.judgement
        known = set(f.evidence_ids)
        references = set(judgement.evidence_ids) | {sid for refs in judgement.requirements.values() for sid in refs}
        if not references.issubset(known) or not set(judgement.calculation_ids).issubset(f.calculation_ids):
            raise ValueError("Judgement cites unavailable evidence/calculations")
        self.require_table_read(references)
        required = set(FACTORS[fid]["required_evidence"])
        if set(judgement.requirements) - required:
            raise ValueError("Unknown requirement IDs")
        met = {key for key, refs in judgement.requirements.items() if refs}
        f.requirements_met = sorted(met)
        f.coverage = len(met) / len(required)
        f.judgement = judgement
        f.status = "CONFLICT" if judgement.conflicts else (
            "FULFILLED" if f.coverage == 1 and not judgement.missing else "PARTIALLY_FULFILLED")
        return self.store.put("judgement", {"factor_id": fid, **judgement.model_dump(),
            "verification": "reference_integrity_checked; semantic_review_pending"}, [parent_id] + f.calculation_ids)

    def require_table_read(self, ids):
        loaded = {sid for f in self.state.factors.values() for sid in f.read_source_ids}
        for row in self.retriever.read(sorted(ids)):
            if row['id'] in ids and table_card(row) and row['id'] not in loaded:
                raise ValueError('Table discovery card is not value evidence; read ' + row['id'])

    def reset_factor(self, fid):
        old = self.state.factors[fid]
        self.store.put("factor_checkpoint", old.model_dump(mode="json"))
        self.state.factors[fid] = FactorState(factor_id=fid, evidence_ids=old.evidence_ids,
            dataset_ids=old.dataset_ids, calculation_ids=old.calculation_ids, inquiry=old.inquiry,
            reframes=old.reframes, recent_source_ids=old.recent_source_ids, read_source_ids=old.read_source_ids)
        self.state.report_id = None
        self.store.event(action="reset_factor", factor_id=fid)
        self.save()

    def synthesize(self):
        completed = {fid: f for fid, f in self.state.factors.items() if f.judgement}
        if not completed:
            raise ValueError("Analyze at least one factor before synthesis")
        context = {"mode": self.state.mode, "review_date": str(self.state.review_date),
            "factors": {fid: {"name": FACTORS[fid]["name"], "state": {"judgement": f.judgement.model_dump()},
                "inquiry": f.inquiry.model_dump() if f.inquiry else None} for fid, f in completed.items()},
            "unanalysed": [fid for fid in FACTORS if fid not in completed],
            "status": "DRAFT_ONLY"}
        request = self.store.put("synthesis_input", context)
        raw = self.client.synthesize(context)
        response = self.store.put("synthesis_raw", {"raw": raw}, [request])
        report = json.loads(raw)
        if not isinstance(report.get("title"), str) or not isinstance(report.get("paragraphs"), list):
            raise ValueError("Invalid report schema")
        for paragraph in report["paragraphs"]:
            refs = paragraph.get("factor_ids", [])
            if not refs or not set(refs).issubset(completed):
                raise ValueError("Report cites unavailable factors")
            evidence = {s for fid in refs for s in completed[fid].evidence_ids}
            calculations = {s for fid in refs for s in completed[fid].calculation_ids}
            if not set(paragraph.get("evidence_ids", [])).issubset(evidence):
                raise ValueError("Unknown report evidence")
            if not set(paragraph.get("calculation_ids", [])).issubset(calculations):
                raise ValueError("Unknown report calculation")
        report.update(status="DRAFT_ONLY", mode=self.state.mode, unanalysed=context["unanalysed"],
            verification="reference_integrity_only; numeric/semantic review required")
        self.state.report_id = self.store.put("report", report, [response])
        self.save()
        return report

    def stream_narrative(self, fid=None):
        """Stream an editorial draft; commit only after a clean stream finish."""
        if fid:
            factor = self.state.factors[fid]
            if not factor.judgement:
                raise ValueError("A supported judgement is required before report writing")
            context = {"name": FACTORS[fid]["name"], "judgement": factor.judgement.model_dump(),
                "calculations": [self.store.get(a)["payload"] for a in factor.judgement.calculation_ids]}
        else:
            if not self.state.report_id:
                raise ValueError("Synthesis is required before final report writing")
            context = self.store.get(self.state.report_id)["payload"]
        request = self.store.put("narrative_input", context)
        chunks = []
        try:
            for chunk in self.client.stream_report(context):
                chunks.append(chunk)
                yield chunk
            text = "".join(chunks).strip()
            if not text:
                raise ValueError("Empty report stream")
            self.store.put("narrative", {"factor_id": fid, "text": text, "status": "DRAFT"}, [request])
            if fid:
                factor.report_text = text
            else:
                revised = dict(context, narrative=text)
                self.state.report_id = self.store.put("report", revised, [self.state.report_id, request])
            self.save()
        except Exception:
            self.store.put("narrative_partial", {"factor_id": fid, "text": "".join(chunks),
                "status": "INTERRUPTED"}, [request])
            raise

    @classmethod
    def resume(cls, root, case_id, run_id, client, executor=None):
        store = Store(root, case_id, run_id)
        state = ReviewState.model_validate_json((store.path / "state.json").read_text(encoding="utf-8"))
        from .models import Source
        artifacts = [json.loads(p.read_text(encoding="utf-8")) for pattern in ("sources_*.json", "manifest_*.json")
                     for p in (store.path / "artifacts").glob(pattern)]
        sources = [Source.model_validate(s) for a in artifacts if a["stage"] == "sources" for s in a["payload"]["sources"]]
        manifest = next(a["payload"] for a in artifacts if a["stage"] == "manifest")
        return cls(store, state, Retriever(sources, state.review_date, manifest["embedding_model"]), client, executor)
