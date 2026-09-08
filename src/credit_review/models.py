from __future__ import annotations

from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Model):
    id: str
    document_id: str
    page: int = Field(ge=1)
    text: str
    kind: str = "paragraph"
    parent_id: str | None = None
    published_at: date
    metadata: dict[str, Any] = Field(default_factory=dict)


class Column(Model):
    name: str
    dtype: Literal["string", "number", "integer", "boolean"]
    unit: str | None = None
    description: str = ""


class Dataset(Model):
    name: str
    description: str
    entity: str
    scope: Literal["SEPARATE", "CONSOLIDATED", "UNKNOWN"]
    value_type: Literal["ACTUAL", "FORECAST", "ASSUMPTION"]
    columns: list[Column]
    rows: list[dict[str, Any]]
    # One map per row, every non-null cell maps to source IDs.
    cell_sources: list[dict[str, list[str]]]
    period_column: str

    @model_validator(mode="after")
    def shape(self):
        names = [c.name for c in self.columns]
        if not names or len(names) != len(set(names)):
            raise ValueError("Columns must be unique and nonempty")
        if self.period_column not in names:
            raise ValueError("period_column must exist")
        if len(self.rows) != len(self.cell_sources) or not self.rows:
            raise ValueError("Each row needs cell provenance")
        for row, refs in zip(self.rows, self.cell_sources):
            if set(row) != set(names) or set(refs) - set(names):
                raise ValueError("Row/provenance columns differ from schema")
            for c in self.columns:
                v = row[c.name]
                if v is None:
                    continue
                valid = {"string": isinstance(v, str),
                         "number": isinstance(v, (int, float)) and not isinstance(v, bool),
                         "integer": isinstance(v, int) and not isinstance(v, bool),
                         "boolean": isinstance(v, bool)}[c.dtype]
                if not valid or not refs.get(c.name):
                    raise ValueError(f"Invalid type or missing provenance: {c.name}")
        return self


class Calculation(Model):
    purpose: str
    dataset_ids: list[str] = Field(min_length=1)
    code: str
    assumptions: list[str] = Field(default_factory=list)


class DatasetCalculation(Model):
    """A plan on the just-extracted dataframe, executed only after validation."""
    purpose: str
    code: str
    assumptions: list[str] = Field(default_factory=list)


class Judgement(Model):
    summary: str
    evidence_ids: list[str]
    calculation_ids: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    mitigants: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    # Requirement IDs from the registry, with supporting source IDs.
    requirements: dict[str, list[str]] = Field(default_factory=dict)


class Inquiry(Model):
    question: str = Field(min_length=1, max_length=300)
    hypotheses: list[str] = Field(min_length=1, max_length=5)
    evidence_tests: list[str] = Field(min_length=1, max_length=6)
    change_reason: str = Field(min_length=1, max_length=500)


class Action(Model):
    action: Literal["plan", "reframe", "search", "read", "dataset", "calculate", "reuse", "conclude"]
    reason: str
    inquiry: Inquiry | None = None
    query: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    reuse_dataset_ids: list[str] = Field(default_factory=list)
    dataset: Dataset | None = None
    calculation: Calculation | None = None
    after_dataset: DatasetCalculation | None = None
    judgement: Judgement | None = None

    @model_validator(mode="after")
    def payload(self):
        if self.after_dataset is not None and self.action != 'dataset':
            raise ValueError('after_dataset is only valid for a dataset action')
        required = {"plan": self.inquiry, "reframe": self.inquiry, "search": self.query, "read": self.source_ids,
                    "dataset": self.dataset, "calculate": self.calculation, "reuse": self.reuse_dataset_ids,
                    "conclude": self.judgement}[self.action]
        if not required:
            raise ValueError(f"Missing payload for {self.action}")
        return self


class FactorAction(Model):
    factor_id: str
    action: Action


class BatchActions(Model):
    actions: list[FactorAction] = Field(min_length=1, max_length=7)


class FactorState(Model):
    factor_id: str
    applicability: Literal["REQUIRED", "OPTIONAL", "NOT_APPLICABLE"] = "REQUIRED"
    status: str = "UNFULFILLED"
    steps: int = 0
    retrieval_stalls: int = 0
    evidence_ids: list[str] = Field(default_factory=list)
    dataset_ids: list[str] = Field(default_factory=list)
    calculation_ids: list[str] = Field(default_factory=list)
    judgement: Judgement | None = None
    error: str | None = None
    recent_source_ids: list[str] = Field(default_factory=list)
    read_source_ids: list[str] = Field(default_factory=list)
    coverage: float = 0
    requirements_met: list[str] = Field(default_factory=list)
    last_signature: str | None = None
    repeated_actions: int = 0
    inquiry: Inquiry | None = None
    reframes: int = 0
    consecutive_errors: int = 0
    failed_response: str | None = None
    report_text: str | None = None


class ReviewState(Model):
    case_id: str
    run_id: str
    review_date: date
    mode: Literal["DEMO", "LIVE"]
    source_revision: str
    factors: dict[str, FactorState]
    generation_status: str = "BLOCKED"
    report_id: str | None = None
    review_strategy: Literal['adaptive', 'grouped', 'sequential_sections'] = 'adaptive'
