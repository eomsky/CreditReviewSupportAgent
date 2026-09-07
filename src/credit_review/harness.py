from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date
from pathlib import Path

from .calculations import DockerExecutor, validate_dataset
from .models import Action, Dataset, FactorState, ReviewState
from .registry import FACTORS
from .retrieval import Retriever
from .store import Store, atomic_json, json_text


class Harness:
    def __init__(self, store: Store, state: ReviewState, retriever: Retriever, client, executor=None):
        self.store, self.state, self.retriever, self.client = store, state, retriever, client
        self.executor = executor or DockerExecutor()
        self.save()

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
        return cls(store, state, Retriever(sources, review_date, embedding_model), client, executor)

    def save(self):
        active = [f for f in self.state.factors.values() if f.applicability != "NOT_APPLICABLE"]
        self.state.generation_status = "DRAFT_ALLOWED" if any(f.judgement for f in active) else "BLOCKED"
        # Final publication requires a later human/semantic verification stage.
        atomic_json(self.store.path / "state.json", self.state.model_dump(mode="json"))

    def context(self, fid):
        factor = self.state.factors[fid]
        return {"factor": FACTORS[fid], "state": factor.model_dump(mode="json"),
                "review_date": str(self.state.review_date), "mode": self.state.mode,
                "sources": self.retriever.read(factor.evidence_ids),
                "datasets": {aid: self.store.get(aid)["payload"] for aid in factor.dataset_ids},
                "calculations": {aid: self.store.get(aid)["payload"] for aid in factor.calculation_ids},
                "available_actions": ["search", "read", "dataset", "calculate", "conclude"]}

    def step(self, fid: str, max_steps: int = 15):
        factor = self.state.factors[fid]
        if factor.judgement or factor.status in ("LIMIT_REACHED", "NO_PROGRESS"):
            return factor
        if factor.steps >= max_steps:
            factor.status = "LIMIT_REACHED"
            self.save()
            return factor
        # Single-writer lease protects against double clicks / concurrent browser sessions.
        lock = self.store.path / ".step.lock"
        with lock.open("x"):
            pass
        request_id = None
        try:
            context = self.context(fid)
            request_id = self.store.put("llm_input", context, factor.dataset_ids + factor.calculation_ids)
            raw = self.client.next_action(context)
            response_id = self.store.put("llm_output", {"raw": raw}, [request_id])
            action = Action.model_validate_json(raw)
            factor.steps += 1
            signature = hashlib.sha256(action.model_dump_json().encode()).hexdigest()
            factor.repeated_actions = factor.repeated_actions + 1 if signature == factor.last_signature else 0
            factor.last_signature = signature
            if factor.repeated_actions >= 2:
                factor.status = "NO_PROGRESS"
                return factor
            result = self.apply(fid, action, response_id)
            factor.error = None
            self.store.event(factor_id=fid, action=action.action, request_id=request_id, output_id=result)
        except Exception as error:
            factor.error = f"{type(error).__name__}: {error}"
            factor.status = "ERROR"
            self.store.event(factor_id=fid, status="ERROR", error=factor.error, request_id=request_id)
        finally:
            lock.unlink(missing_ok=True)
            self.save()
        return factor

    def apply(self, fid, action: Action, parent_id: str):
        f = self.state.factors[fid]
        f.status = "IN_PROGRESS"
        if action.action in ("search", "read"):
            if action.action == "search":
                hits = self.retriever.search(action.query)
                rows = [h["source"] for h in hits]
                payload = {"query": action.query, "hits": hits}
            else:
                rows = self.retriever.read(action.source_ids)
                payload = {"sources": rows}
            f.evidence_ids = sorted(set(f.evidence_ids) | {s["id"] for s in rows})
            return self.store.put(action.action, payload, [parent_id])
        if action.action == "dataset":
            data = action.dataset
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

    def reset_factor(self, fid):
        old = self.state.factors[fid]
        self.store.put("factor_checkpoint", old.model_dump(mode="json"))
        self.state.factors[fid] = FactorState(factor_id=fid, evidence_ids=old.evidence_ids,
            dataset_ids=old.dataset_ids, calculation_ids=old.calculation_ids)
        self.state.report_id = None
        self.store.event(action="reset_factor", factor_id=fid)
        self.save()

    def synthesize(self):
        completed = {fid: f for fid, f in self.state.factors.items() if f.judgement}
        if not completed:
            raise ValueError("Analyze at least one factor before synthesis")
        context = {"mode": self.state.mode, "review_date": str(self.state.review_date),
            "factors": {fid: self.context(fid) for fid in completed},
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

    @classmethod
    def resume(cls, root, case_id, run_id, client, executor=None):
        store = Store(root, case_id, run_id)
        state = ReviewState.model_validate_json((store.path / "state.json").read_text(encoding="utf-8"))
        from .models import Source
        artifacts = store.artifacts()
        sources = [Source.model_validate(s) for a in artifacts if a["stage"] == "sources" for s in a["payload"]["sources"]]
        manifest = next(a["payload"] for a in artifacts if a["stage"] == "manifest")
        return cls(store, state, Retriever(sources, state.review_date, manifest["embedding_model"]), client, executor)
