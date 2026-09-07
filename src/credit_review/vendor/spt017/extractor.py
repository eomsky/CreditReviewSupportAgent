from __future__ import annotations
import json, math, re, statistics, hashlib
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
import fitz

class PDFExtractor:
    """원문 좌표와 물리 표 기하를 보존하는 1단계 추출기."""
    def extract(self, pdf_path, start_page=0, end_page=None):
        pages=[]; physical_tables=[]
        with fitz.open(pdf_path) as doc:
            for pi in range(start_page, len(doc) if end_page is None else min(end_page,len(doc))):
                page=doc[pi]
                pno=pi+1; blocks=[]; sizes=[]
                raw=page.get_text("dict",flags=fitz.TEXTFLAGS_DICT)
                for bi,b in enumerate(raw.get("blocks",[])):
                    if b.get("type")!=0: continue
                    spans=[]; lines=[]
                    for ln in b.get("lines",[]):
                        line_spans=[]
                        for s in ln.get("spans",[]):
                            item={"text":s.get("text",""),"bbox":list(map(float,s["bbox"])),
                                  "size":float(s.get("size",0)),"font":s.get("font",""),
                                  "flags":int(s.get("flags",0)),"color":int(s.get("color",0))}
                            line_spans.append(item); spans.append(item)
                            if item["text"].strip(): sizes.append(item["size"])
                        if line_spans: lines.append({"bbox":list(map(float,ln["bbox"])),"spans":line_spans})
                    text="\n".join("".join(s["text"] for s in ln["spans"]) for ln in lines).strip()
                    if text:
                        blocks.append({"element_id":f"P{pno:04d}_B{bi:05d}","page":pno,
                            "bbox":list(map(float,b["bbox"])),"text":text,"lines":lines,
                            "reading_order":len(blocks),"font_size_max":max((s["size"] for s in spans),default=0),
                            "font_size_median":statistics.median([s["size"] for s in spans]) if spans else 0})
                try: found=list(page.find_tables().tables)
                except Exception as e: found=[]
                for ti,t in enumerate(found,1):
                    matrix=t.extract() or []; cells=[]
                    # PyMuPDF의 t.cells 평탄화 순서는 병합 셀에서 matrix 좌표와 다를 수 있다.
                    # 행/열 좌표를 TableRow에서 직접 보존해야 Annotation 색상이 다른 셀로 이동하지 않는다.
                    for ri,row_obj in enumerate(list(t.rows or [])):
                        for ci,cb in enumerate(list(row_obj.cells or [])):
                            if cb is not None:
                                cells.append({"physical_cell_index":len(cells),"row":ri,"column":ci,
                                              "bbox":list(map(float,cb))})
                    physical_tables.append({"table_id":f"P{pno:04d}_T{ti:03d}","page":pno,
                        "page_width":float(page.rect.width),"page_height":float(page.rect.height),
                        "bbox":list(map(float,t.bbox)),"matrix":matrix,"cell_geometry":cells})
                pages.append({"page":pno,"width":float(page.rect.width),"height":float(page.rect.height),
                              "body_font_size":statistics.median(sizes) if sizes else 10.0,"blocks":blocks})
        return {"source_pdf":Path(pdf_path).name,"page_count":len(pages),"pages":pages,
                "physical_tables":physical_tables}
