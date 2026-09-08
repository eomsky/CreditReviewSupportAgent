"""Report-only projection. Internal coverage/missing lists never enter this view."""
import json
from .registry import FACTORS
from .report_plan import REPORT_SECTIONS, FACTOR_HEADINGS
from .monetary_review import apply_monetary_review

SECTIONS = [(section["title"], list(section["factor_ids"])) for section in REPORT_SECTIONS]


def report_document(h, apply_final_review=True):
    """Keep factual qualifications in analysis; omit operational checklists."""
    sections = []
    displayed_datasets = set()
    for title, ids in SECTIONS:
        paragraphs, tables = [], []
        for fid in ids:
            f = h.state.factors[fid]
            if title == '재무 분석':
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
                paragraphs.append({"heading": FACTOR_HEADINGS[fid], "text": f.report_text})
                continue
            if f.judgement:
                paragraphs.append({"heading": FACTOR_HEADINGS[fid], "text": f.judgement.summary})
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
    report = {"title": "주요여신위험 및 종합심사의견", "case_id": h.state.case_id,
              "review_date": str(h.state.review_date), "mode": h.state.mode,
              "sections": sections, "draft": True}
    review_path = h.store.path / "monetary_review.json"
    if apply_final_review and review_path.exists():
        try:
            report = apply_monetary_review(report, json.loads(review_path.read_text(encoding="utf-8")))
        except Exception:
            # A stale or malformed audit must never replace the evidence-backed report.
            pass
    return report


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
