"""Final, read-only audit of monetary expressions in a completed report."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
import re
from typing import Literal

from pydantic import Field

from .models import Model
from .store import atomic_json


MONEY_FRAGMENT = re.compile(
    r"^\s*[()\-+△▲]?\s*(?:(?:KRW|USD|EUR|JPY|CNY)\s*)?"
    r"\d[\d,]*(?:\.\d+)?\s*[)]?\s*(?:원|천원|백만원|억원|조원|천|USD천|천USD|달러|USD|KRW|EUR|JPY|CNY)"
    r"\s*[)]?\s*$",
    re.IGNORECASE,
)
CANCELLATION_MARKERS = ("~~", "<s>", "</s>", "<del>", "</del>", "\u0336")
KRW_MULTIPLIERS = {
    "조원": Decimal("1000000000000"),
    "억원": Decimal("100000000"),
    "백만원": Decimal("1000000"),
    "천원": Decimal("1000"),
    "원": Decimal("1"),
    "KRW": Decimal("1"),
}


class MonetaryEdit(Model):
    path: str
    old: str
    new: str
    occurrence: int = Field(default=1, ge=1, le=20)
    kind: Literal["amount", "cancellation"]
    reason: str = Field(default="", max_length=300)


class MonetaryReview(Model):
    edits: list[MonetaryEdit] = Field(default_factory=list, max_length=60)


def report_fingerprint(report: dict) -> str:
    raw = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()


def text_paths(value, prefix=""):
    """Return stable JSON-pointer-like paths for every report string."""
    found = {}
    if isinstance(value, str):
        found[prefix or "/"] = value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.update(text_paths(item, f"{prefix}/{index}"))
    elif isinstance(value, dict):
        for key, item in value.items():
            token = str(key).replace("~", "~0").replace("/", "~1")
            found.update(text_paths(item, f"{prefix}/{token}"))
    return found


def _remove_cancellation_marks(value: str) -> str:
    for marker in CANCELLATION_MARKERS:
        value = value.replace(marker, "")
    return value


def _number_and_krw_unit(value: str):
    number = re.search(r"\d[\d,]*(?:\.\d+)?", value)
    unit = next((item for item in KRW_MULTIPLIERS if item.lower() in value.lower()), None)
    if not number or not unit:
        return None
    try:
        return Decimal(number.group(0).replace(",", "")), unit
    except InvalidOperation:
        return None


def _same_krw_value_after_rounding(old: str, new: str) -> bool:
    source = _number_and_krw_unit(old)
    target = _number_and_krw_unit(new)
    if not source or not target:
        return False
    source_number, source_unit = source
    target_number, target_unit = target
    expected = (source_number * KRW_MULTIPLIERS[source_unit] / KRW_MULTIPLIERS[target_unit]).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP)
    return target_number == expected


def _valid_edit(edit: MonetaryEdit, original: str) -> bool:
    if not edit.old or edit.old == edit.new:
        return False
    if original.count(edit.old) < edit.occurrence:
        return False
    if edit.kind == "cancellation":
        return any(marker in edit.old for marker in CANCELLATION_MARKERS) and _remove_cancellation_marks(edit.old) == edit.new
    if not MONEY_FRAGMENT.fullmatch(edit.old) or not MONEY_FRAGMENT.fullmatch(edit.new):
        return False
    number = re.search(r"\d[\d,]*(?:\.\d+)?", edit.new)
    if number and "." in number.group(0):
        return False
    # A monetary correction may change only the selected monetary token.  Korean
    # won output must use the requested normalized unit and contain no decimals.
    lowered = edit.new.lower()
    if any(unit in lowered for unit in ("원", "krw")):
        if not ("백만원" in edit.new or "억원" in edit.new):
            return False
        numeric = abs(int(number.group(0).replace(",", ""))) if number else 0
        if "백만원" in edit.new and numeric > 1000:
            return False
        if "억원" in edit.new and numeric < 10:
            return False
        if not _same_krw_value_after_rounding(edit.old, edit.new):
            return False
    return True


def _replace_spans(original: str, edits: list[MonetaryEdit]) -> str:
    spans = []
    for edit in edits:
        start = -1
        cursor = 0
        for _ in range(edit.occurrence):
            start = original.find(edit.old, cursor)
            if start < 0:
                break
            cursor = start + len(edit.old)
        if start < 0:
            raise ValueError("Monetary edit target was not found")
        spans.append((start, start + len(edit.old), edit.new))
    spans.sort(reverse=True)
    for (start, end, _), (next_start, next_end, _) in zip(spans, spans[1:]):
        if next_end > start:
            raise ValueError("Monetary edits overlap")
    revised = original
    for start, end, replacement in spans:
        revised = revised[:start] + replacement + revised[end:]
    return revised


def apply_monetary_review(report: dict, record: dict) -> dict:
    """Compatibility shim: the monetary audit never mutates report content."""
    return deepcopy(report)


def run_monetary_review(h, client, report: dict):
    """Make one final LLM call and persist validated findings without applying them."""
    base = deepcopy(report)
    fingerprint = report_fingerprint(base)
    path = h.store.path / "monetary_review.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("status") == "COMPLETED" and existing.get("input_fingerprint") == fingerprint:
            return existing
    available = text_paths(base)
    raw = client.review_monetary_report({"report": base, "allowed_paths": sorted(available)})
    # Keep the exact response when validation fails so the final audit can be
    # diagnosed and resumed without regenerating the completed report body.
    raw_path = h.store.path / "monetary_review_raw.txt"
    raw_path.write_text(raw, encoding="utf-8")
    try:
        review = MonetaryReview.model_validate_json(raw)
    except Exception as exc:
        atomic_json(h.store.path / "monetary_review_failure.json", {
            "status": "FAILED",
            "input_fingerprint": fingerprint,
            "error": str(exc),
            "raw_response": raw[:12000],
        })
        raise
    accepted = [edit for edit in review.edits
                if edit.path in available and _valid_edit(edit, available[edit.path])]
    candidate = {
        "status": "COMPLETED",
        "input_fingerprint": fingerprint,
        "findings": [edit.model_dump() for edit in accepted],
        "rejected_finding_count": len(review.edits) - len(accepted),
    }
    atomic_json(path, candidate)
    (h.store.path / "monetary_review_failure.json").unlink(missing_ok=True)
    return candidate
