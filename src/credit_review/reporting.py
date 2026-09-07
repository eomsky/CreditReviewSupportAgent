"""Report-only projection. Internal coverage/missing lists never enter this view."""
from .registry import FACTORS

SECTIONS = [
    ("기업 개요 및 지배구조", ["F01", "F02", "F03", "F04", "F05"]),
    ("여신 신청내용 및 거래구조", ["F27", "F28"]),
    ("산업환경 및 사업성", [f"F{i:02}" for i in range(6, 13)]),
    ("재무현황 및 수익성", [f"F{i:02}" for i in range(13, 21)]),
    ("차입구조 및 상환능력", ["F21", "F22", "F23", "F24"]),
    ("담보·우발채무 및 주요 위험", ["F25", "F26", "F30"]),
    ("당행 거래 및 수익성", ["F29"]),
]


def report_document(h):
    """Keep factual qualifications in analysis; omit operational checklists."""
    sections = []
    seen_data, seen_calcs = set(), set()
    for title, ids in SECTIONS:
        paragraphs, tables = [], []
        for fid in ids:
            f = h.state.factors[fid]
            if f.judgement:
                paragraphs.append({"heading": FACTORS[fid]["name"], "text": f.judgement.summary})
                # Risks/mitigants are substantive analysis, unlike internal missing slots.
                for label, values in [("위험요인", f.judgement.risks), ("완화요인", f.judgement.mitigants)]:
                    if values:
                        paragraphs.append({"heading": label, "text": " ".join(values)})
            for aid in f.dataset_ids:
                if aid in seen_data:
                    continue
                seen_data.add(aid)
                data = h.store.get(aid)["payload"]
                tables.append({"caption": data["description"],
                    "columns": [c["name"] + (f" ({c['unit']})" if c.get("unit") else "") for c in data["columns"]],
                    "rows": [[row[c["name"]] for c in data["columns"]] for row in data["rows"]]})
            for aid in f.calculation_ids:
                if aid in seen_calcs:
                    continue
                seen_calcs.add(aid)
                data = h.store.get(aid)["payload"]
                result = data.get("result")
                if isinstance(result, dict):
                    tables.append({"caption": data["plan"]["purpose"], "columns": ["산출 항목", "결과"],
                        "rows": [[k, str(v)] for k, v in result.items()]})
                else:
                    paragraphs.append({"heading": data["plan"]["purpose"], "text": str(result)})
                if data["plan"].get("assumptions"):
                    paragraphs.append({"heading": "산출 기준", "text": " ".join(data["plan"]["assumptions"])})
        if paragraphs or tables:
            sections.append({"title": title, "paragraphs": paragraphs, "tables": tables})
    if h.state.report_id:
        raw = h.store.get(h.state.report_id)["payload"]
        sections.append({"title": "종합심사의견", "paragraphs": [
            {"heading": "", "text": p["text"]} for p in raw["paragraphs"]], "tables": []})
    return {"title": "주요여신위험 및 종합심사의견", "case_id": h.state.case_id,
            "review_date": str(h.state.review_date), "mode": h.state.mode,
            "sections": sections, "draft": True}


def report_markdown(report):
    def cell(v):
        return str(v if v is not None else "—").replace("|", "\\|").replace("\n", " ")
    lines = ["# " + report["title"], "", f"심사건: {report['case_id']} · 기준일: {report['review_date']} · 검토용 초안", ""]
    if report["mode"] == "DEMO":
        lines += ["가상 자료 예시", ""]
    for i, section in enumerate(report["sections"], 1):
        lines += [f"## {i}. {section['title']}", ""]
        for paragraph in section["paragraphs"]:
            if paragraph["heading"]:
                lines += ["**" + paragraph["heading"] + "**", ""]
            lines += [paragraph["text"], ""]
        for table in section["tables"]:
            lines += [table["caption"], "", "| " + " | ".join(map(cell, table["columns"])) + " |",
                      "| " + " | ".join("---" for _ in table["columns"]) + " |"]
            lines += ["| " + " | ".join(map(cell, row)) + " |" for row in table["rows"]]
            lines += [""]
    return "\n".join(lines)
