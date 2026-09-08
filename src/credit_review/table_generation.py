"""One-call, evidence-bound table placement for a completed review report."""
from __future__ import annotations

from copy import deepcopy
import json
import re

from pydantic import Field, model_validator

from .models import Model
from .monetary_review import (
    _same_krw_value_after_rounding,
    report_fingerprint,
    text_paths,
)
from .store import atomic_json


NUMBER = re.compile(r"(?<![A-Za-z0-9])\d[\d,]*(?:\.\d+)?%?")
MONEY = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:조원|억원|백만원|천원|원|KRW)",
    re.IGNORECASE,
)


class GeneratedTableRow(Model):
    cells: list[str] = Field(min_length=2, max_length=7)
    source_paths: list[str] = Field(min_length=1, max_length=10)


class GeneratedTable(Model):
    section_index: int = Field(ge=0, le=12)
    after_paragraph_index: int = Field(ge=-1, le=60)
    caption: str = Field(min_length=2, max_length=160)
    columns: list[str] = Field(min_length=2, max_length=7)
    rows: list[GeneratedTableRow] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def rectangular(self):
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("Table columns must be unique")
        if any(len(row.cells) != len(self.columns) for row in self.rows):
            raise ValueError("Every table row must match the column count")
        return self


class TablePlan(Model):
    tables: list[GeneratedTable] = Field(default_factory=list, max_length=10)


def _same_krw_value(left: str, right: str) -> bool:
    return _same_krw_value_after_rounding(right, left)


def _row_is_grounded(row: GeneratedTableRow, available: dict[str, str]) -> bool:
    if any(path not in available for path in row.source_paths):
        return False
    evidence = " ".join(available[path] for path in row.source_paths)
    source_money = MONEY.findall(evidence)
    for cell in row.cells:
        for token in NUMBER.findall(cell):
            plain = token.removesuffix("%")
            if token in evidence or plain in evidence:
                continue
            containing = next((amount for amount in MONEY.findall(cell) if plain in amount), None)
            if containing and any(_same_krw_value(containing, amount) for amount in source_money):
                continue
            return False
    return True


def _validated_tables(report: dict, raw_tables: list[dict]) -> list[GeneratedTable]:
    available = text_paths(report)
    accepted = []
    for raw in raw_tables:
        try:
            table = GeneratedTable.model_validate(raw)
        except Exception:
            continue
        if table.section_index >= len(report.get("sections", [])):
            continue
        paragraphs = report["sections"][table.section_index].get("paragraphs", [])
        if table.after_paragraph_index >= len(paragraphs):
            continue
        if not all(_row_is_grounded(row, available) for row in table.rows):
            continue
        accepted.append(table)
    return accepted


def apply_table_plan(report: dict, record: dict) -> dict:
    if record.get("status") != "COMPLETED" or record.get("input_fingerprint") != report_fingerprint(report):
        return report
    raw_tables = record.get("tables", [])
    if not raw_tables:
        return report
    tables = _validated_tables(report, raw_tables)
    if not tables:
        return report
    revised = deepcopy(report)
    for section in revised.get("sections", []):
        section["tables"] = []
    for table in tables:
        revised["sections"][table.section_index]["tables"].append({
            "caption": table.caption,
            "columns": table.columns,
            "rows": [row.cells for row in table.rows],
            "after_paragraph_index": table.after_paragraph_index,
        })
    return revised


def run_table_generation(h, client, report: dict):
    """Make the ninth LLM call and persist only grounded, positioned tables."""
    base = deepcopy(report)
    fingerprint = report_fingerprint(base)
    path = h.store.path / "table_generation.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("status") == "COMPLETED" and existing.get("input_fingerprint") == fingerprint:
            return existing
    available = text_paths(base)
    placement = [{
        "section_index": index,
        "title": section["title"],
        "paragraphs": [{"paragraph_index": p_index, "heading": paragraph.get("heading", "")}
                       for p_index, paragraph in enumerate(section.get("paragraphs", []))],
    } for index, section in enumerate(base.get("sections", []))]
    raw = client.generate_report_tables({
        "report": base,
        "allowed_source_paths": sorted(available),
        "placement_map": placement,
    })
    plan = TablePlan.model_validate_json(raw)
    accepted = _validated_tables(base, [table.model_dump() for table in plan.tables])
    if plan.tables and not accepted:
        raise ValueError("Table generation returned no evidence-grounded tables")
    record = {
        "status": "COMPLETED",
        "input_fingerprint": fingerprint,
        "tables": [table.model_dump() for table in accepted],
    }
    atomic_json(path, record)
    return record
