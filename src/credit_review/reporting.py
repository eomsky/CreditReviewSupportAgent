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
    displayed_datasets = set()
    for title, ids in SECTIONS:
        paragraphs, tables = [], []
        for fid in ids:
            f = h.state.factors[fid]
            if title == '재무현황 및 수익성':
                for aid in f.dataset_ids:
                    if aid in displayed_datasets: continue
                    displayed_datasets.add(aid)
                    data = h.store.get(aid)['payload']
                    columns=data['columns']
                    def value(v):
                        if isinstance(v,(float,int)) and not isinstance(v,bool):
                            return format(v,',.2f').rstrip('0').rstrip('.') if isinstance(v,float) else format(v,',d')
                        return v
                    scope={'CONSOLIDATED':'연결','SEPARATE':'별도','UNKNOWN':'범위 미확인'}[data['scope']]
                    tables.append({'caption':f"{data['entity']} · {scope} · {data['name']}",
                        'columns':[(c.get('description') or c['name'])+(f" ({c['unit']})" if c.get('unit') else '') for c in columns],
                        'rows':[[value(row[c['name']]) for c in columns] for row in data['rows']]})
            if f.report_text:
                paragraphs.append({"heading": FACTORS[fid]["name"], "text": f.report_text})
                continue
            if f.judgement:
                paragraphs.append({"heading": FACTORS[fid]["name"], "text": f.judgement.summary})
                # Risks/mitigants are substantive analysis, unlike internal missing slots.
                for label, values in [("위험요인", f.judgement.risks), ("완화요인", f.judgement.mitigants)]:
                    if values:
                        paragraphs.append({"heading": label, "text": " ".join(values)})
        if paragraphs or tables:
            sections.append({"title": title, "paragraphs": paragraphs, "tables": tables})
    if h.state.report_id:
        raw = h.store.get(h.state.report_id)["payload"]
        paragraphs = [{"heading": "", "text": raw["narrative"]}] if raw.get("narrative") else [
            {"heading": "", "text": p["text"]} for p in raw["paragraphs"]]
        sections.append({"title": "종합심사의견", "paragraphs": paragraphs, "tables": []})
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
