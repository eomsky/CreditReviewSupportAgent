from __future__ import annotations
import json, math, re, statistics, hashlib
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np
import fitz

VERSION="v0.17"

class DocumentBuilder:
    UNIT_RX=re.compile(r"(?:\(\s*단위\s*[:：].*?\)|단위\s*[:：]\s*[^\n]{1,50}|unit\s*[:：]\s*[^\n]{1,50})",re.I)
    NOTE_RX=re.compile(r"^(?:주\s*\d*\)|※|\*|자료\s*[:：]|출처\s*[:：])")
    PERIOD_RX=re.compile(r"(?:당기|전기|전전기|기초|기말|제\s*\d+\s*기|(?:19|20)\d{2}(?:[./-]\d{1,2}){0,2})")
    TOTAL_RX=re.compile(r"^(?:합\s*계|총\s*계|소\s*계|누\s*계|계)$")

    def build(self, raw):
        self.raw=raw; self.pages={p["page"]:p for p in raw["pages"]}
        tables=[self._normalize_table(t) for t in raw["physical_tables"]]
        links=self._continuity_links(tables)
        self._assign_logical_ids(tables,links)
        model,model_info=self._prepare_boundary_model(tables)
        logical_inference=self._infer_logical_roles(tables,links,model)
        self._apply_continuation_semantics(tables,links)
        self._attach_context(tables)
        self._inherit_units(tables,links)
        self._link_logical_context(tables)
        headings,furniture,body=self._document_regions(tables)
        annotation=self._annotation(tables,headings,furniture,body,links)
        return {"schema_name":"SEMANTIC_PROMPT_TRANSFER","schema_version":"0.13",
            "source_document":{"file_name":raw["source_pdf"],"page_count":raw["page_count"],
                "page_number_base":1,"bbox_format":["x0","y0","x1","y1"]},
            "processing_policy":{"table_order":"CONTINUITY_BEFORE_ROLE_CONFIRMATION",
                "region_model":"JointRectangularExtraTreesClassifier","uncertainty":"PRESERVED","value_rectangle_required":True,"region_postprocess":"FORBIDDEN"},
            "model_info":model_info,"logical_table_inference":logical_inference,"raw_document":raw,"table_continuity":links,
            "semantic_elements":{"tables":tables,"headings":headings},"annotation":annotation}

    def _clean(self,x): return re.sub(r"\s+"," ",str(x or "")).strip()
    def _numeric(self,x):
        s=self._clean(x).replace(",","").replace("−","-")
        if not s or s in {"-","–","—"}: return None
        neg=s.startswith("(") and s.endswith(")")
        if neg:s=s[1:-1]
        s=re.sub(r"[%원주명건회배천백만원달러USD₩$]","",s).strip()
        try:return -float(s) if neg else float(s)
        except:return None

    def _normalize_table(self,t):
        matrix=[[self._clean(x) for x in row] for row in (t.get("matrix") or [])]
        width=max((len(r) for r in matrix),default=0)
        matrix=[r+[""]*(width-len(r)) for r in matrix]
        return {**t,"matrix":matrix,"row_count":len(matrix),"column_count":width,
                "status":"UNRESOLVED","title":None,"units":[],"notes":[],"period_context":[]}

    def _signature(self,t):
        m=t["matrix"]; cols=t["column_count"]
        x0,_,x1,_=t["bbox"]; width=max(1,x1-x0)
        if cols: xs=[round((i+.5)/cols,3) for i in range(cols)]
        else: xs=[]
        kinds=[]
        for c in range(cols):
            vals=[r[c] for r in m if r[c]]
            kinds.append(round(sum(self._numeric(v) is not None for v in vals)/max(1,len(vals)),2))
        return xs,kinds



    def _continuation_profile(self,t):
        cells=[self._clean(x) for row in t["matrix"] for x in row if self._clean(x)]
        numeric=sum(self._numeric(x) is not None for x in cells)/max(1,len(cells))
        periods=sum(bool(self.PERIOD_RX.search(x)) for x in cells)
        header_only=t["row_count"]<=2 and numeric<.18 and periods>=2
        body_only=t["row_count"]>=2 and numeric>=.22
        return {"numeric_ratio":numeric,"period_count":periods,
                "header_only":header_only,"body_only":body_only}

    def _continuity_score(self,a,b,boundary_priority=False):
        if b["page"]!=a["page"]+1:return 0,[],None
        ev=[]; score=0
        edge_a=a["bbox"][3]/a["page_height"]>=.82; edge_b=b["bbox"][1]/b["page_height"]<=.22
        if edge_a:score+=.22;ev.append("BOTTOM_EDGE")
        if edge_b:score+=.22;ev.append("TOP_EDGE")
        if boundary_priority and edge_a and edge_b:score+=.12;ev.append("EXCLUSIVE_PAGE_BOUNDARY_PAIR")
        if a["column_count"]==b["column_count"] and a["column_count"]>1:score+=.22;ev.append("SAME_COLUMNS")
        ax,ak=self._signature(a); bx,bk=self._signature(b)
        if ax and len(ax)==len(bx):
            sim=1-float(np.mean(np.abs(np.asarray(ax)-np.asarray(bx))))
            score+=.20*max(0,sim);ev.append(f"COLUMN_SIGNATURE_{sim:.3f}")
        aw=(a["bbox"][2]-a["bbox"][0])/a["page_width"];bw=(b["bbox"][2]-b["bbox"][0])/b["page_width"]
        align=max(0,1-abs(a["bbox"][0]/a["page_width"]-b["bbox"][0]/b["page_width"])-abs(aw-bw))
        score+=.14*align
        pa,pb=self._continuation_profile(a),self._continuation_profile(b)
        link_type=None
        if edge_a and edge_b and align>=.88 and pa["header_only"] and pb["body_only"]:
            score=max(score,.92);link_type="HEADER_BODY_CONTINUATION"
            ev.extend(["HEADER_ONLY_PREDECESSOR","BODY_ONLY_SUCCESSOR","LOGICAL_WIDTH_ALIGNMENT"])
        elif (a["row_count"]<=2 and a["column_count"]<b["column_count"] and
              pa["period_count"]>=2 and align>=.90):
            score+=.20;link_type="EXPANDED_HEADER_CONTINUATION"
            ev.append("PARENT_HEADER_EXPANDS_TO_CHILD_COLUMNS")
        return round(min(1,score),4),list(dict.fromkeys(ev)),link_type


    def _continuity_links(self,tables):
        by_page=defaultdict(list)
        for t in tables:by_page[t["page"]].append(t)
        links=[]
        for page in sorted(by_page):
            if page+1 not in by_page:continue
            a=max(by_page[page],key=lambda t:t["bbox"][3])
            b=min(by_page[page+1],key=lambda t:t["bbox"][1])
            score,ev,link_type=self._continuity_score(a,b,True)
            decisive=link_type=="HEADER_BODY_CONTINUATION"
            if score>=.58 or decisive:
                evidence_set=set(ev);both_edges={"BOTTOM_EDGE","TOP_EDGE"}.issubset(evidence_set)
                same_columns=a["column_count"]==b["column_count"] and a["column_count"]>1
                last_values=[self._clean(value) for value in a["matrix"][-1]]
                first_nonblank=next((value for value in last_values if value),"")
                complete_total=bool(self.TOTAL_RX.fullmatch(first_nonblank))
                structurally_closed=complete_total or not both_edges or not same_columns
                status="CONFIRMED" if decisive or (score>=.68 and not structurally_closed) else "REVIEW_REQUIRED"
                if structurally_closed and not decisive:ev.append("DETERMINISTIC_CLOSURE_OR_GEOMETRY_REVIEW")
                links.append({"from":a["table_id"],"to":b["table_id"],"score":score,
                              "evidence":ev,"status":status,
                              "link_type":link_type or "GEOMETRIC_CONTINUATION"})
        return links

    def _assign_logical_ids(self,tables,links):
        parent={t["table_id"]:t["table_id"] for t in tables}
        def find(x):
            while parent[x]!=x: parent[x]=parent[parent[x]];x=parent[x]
            return x
        for l in links:
            if l["status"]=="CONFIRMED":parent[find(l["to"])]=find(l["from"])
        groups={}
        for t in tables:
            root=find(t["table_id"]); groups.setdefault(root,f"LT_{len(groups)+1:05d}")
            t["logical_table_id"]=groups[root]
            t["continuation_role"]="SEGMENT" if any(l["from"]==t["table_id"] or l["to"]==t["table_id"] for l in links) else "SINGLE"

    HEADER_TERMS=("구분","종류","항목","명칭","기준일","당기","전기","연도","기간","금액","비율","수량","회사명","기업명","소재국","단위","기초","증가","감소","기말","합계","장부금액","공정가치")
    FEATURE_NAMES=[
        "h_norm","s_norm","rows_norm","cols_norm",
        "header_density","header_numeric","header_term","header_missing","header_len",
        "stub_density","stub_numeric","stub_header_term","stub_missing","stub_len",
        "value_density","value_numeric","value_header_term","value_missing","value_len",
        "stub_minus_value_numeric","stub_minus_value_terms","value_minus_header_numeric",
        "header_blank_ratio","body_blank_transition","top_merge_proxy","left_merge_proxy",
        "value_area_ratio","header_exists","stub_width_one",
        "row_before_numeric","row_after_numeric","row_before_header_term","row_after_header_term",
        "col_before_numeric","col_after_numeric","col_before_header_term","col_after_header_term",
        "header_merge_end_support","stub_merge_end_support","header_crossing_rate","stub_crossing_rate",
        "header_parent_child_support","body_vertical_merge_support"
    ]

    def _region_stats(self,values):
        z=[self._clean(x) for x in values]; non=[x for x in z if x]; n=max(1,len(z)); nn=max(1,len(non))
        return [len(non)/n,
                sum(self._numeric(x) is not None for x in non)/nn,
                sum(any(k in x for k in self.HEADER_TERMS) for x in non)/nn,
                sum(x in {"-","–","—","N/A","해당없음"} for x in non)/nn,
                statistics.mean([min(80,len(x))/80 for x in non]) if non else 0.0]

    def _pair_features(self,matrix,h,s,merges=None):
        rows=len(matrix);cols=len(matrix[0]) if matrix else 0
        merges=merges or []
        header=[x for row in matrix[:h] for x in row]
        stub=[matrix[r][c] for r in range(h,rows) for c in range(s)]
        value=[matrix[r][c] for r in range(h,rows) for c in range(s,cols)]
        hs,ss,vs=self._region_stats(header),self._region_stats(stub),self._region_stats(value)
        blank_transition=sum(bool(not self._clean(matrix[r][c-1]) and self._clean(matrix[r][c])) for r in range(h,rows) for c in range(1,cols))/max(1,(rows-h)*(cols-1))
        # Excel/PDF 병합의 사람이 보는 흔적: 부모 셀 뒤의 공백과 좌측 수직 반복.
        top_merge=sum(bool(self._clean(matrix[r][c-1]) and not self._clean(matrix[r][c])) for r in range(h) for c in range(1,cols))/max(1,h*(cols-1))
        left_merge=sum(bool(not self._clean(matrix[r][c]) and r>h and self._clean(matrix[r-1][c])) for r in range(h,rows) for c in range(s))/max(1,(rows-h)*s)
        row_before=self._region_stats(matrix[h-1] if h>0 else [])
        row_after=self._region_stats(matrix[h] if h<rows else [])
        col_before=self._region_stats([matrix[r][s-1] for r in range(h,rows)] if s>0 else [])
        col_after=self._region_stats([matrix[r][s] for r in range(h,rows)] if s<cols else [])
        header_merges=[m for m in merges if m["row"]<max(1,h)]
        body_merges=[m for m in merges if m["row"]>=h]
        header_end=sum(m["row"]+m["row_span"]==h for m in header_merges)/max(1,len(header_merges))
        stub_end=sum(m["column"]+m["col_span"]==s for m in body_merges)/max(1,len(body_merges))
        h_cross=sum(m["row"]<h<m["row"]+m["row_span"] for m in merges)/max(1,len(merges))
        s_cross=sum(m["column"]<s<m["column"]+m["col_span"] and m["row"]>=h for m in merges)/max(1,len(merges))
        parent_child=sum(m["row"]<h and m["col_span"]>1 and m["row"]+m["row_span"]<=h for m in merges)/max(1,len(header_merges))
        body_vertical=sum(m["row"]>=h and m["row_span"]>1 and m["column"]<s for m in merges)/max(1,len(body_merges))
        return [h/max(1,rows),s/max(1,cols),min(rows,80)/80,min(cols,40)/40,
                *hs,*ss,*vs,ss[1]-vs[1],ss[2]-vs[2],vs[1]-hs[1],
                sum(not self._clean(x) for x in header)/max(1,len(header)),blank_transition,
                top_merge,left_merge,((rows-h)*(cols-s))/max(1,rows*cols),float(h>0),float(s==1),
                row_before[1],row_after[1],row_before[2],row_after[2],col_before[1],col_after[1],col_before[2],col_after[2],header_end,stub_end,h_cross,s_cross,parent_child,body_vertical]


    def _candidate_rows(self,matrix,merges=None,allow_full_header=False):
        rows=len(matrix);cols=len(matrix[0]) if matrix else 0
        # A standalone physical table must retain local DATA rows.  A segment
        # inside a deterministically confirmed logical table may be entirely
        # HEADER because a later segment supplies the required DATA rectangle.
        stop=rows+1 if allow_full_header else rows
        return [(h,s,self._pair_features(matrix,h,s,merges)) for h in range(stop) for s in range(1,cols)]



    def _predict_boundaries(self,matrix,bundle,merges=None,allow_headerless=False,fixed_stub=None):
        candidates=self._candidate_rows(matrix,merges)
        if fixed_stub is not None:candidates=[c for c in candidates if c[1]==fixed_stub]
        if not candidates:return 0,0,0.0,[]
        probs=bundle["joint_model"].predict_proba([x[2] for x in candidates])[:,1]
        pi0=float(bundle.get("header_zero_rate",.01));strength=.25
        penalty=min(1.25,strength*np.log(max(1e-6,(1-pi0)/max(1e-6,pi0))))
        scores=np.asarray([np.log(max(1e-9,p)/max(1e-9,1-p))-penalty*int(c[0]==0 and not allow_headerless) for c,p in zip(candidates,probs)])
        i=int(np.argmax(scores));h,s=candidates[i][:2]
        return h,s,float(probs[i]),[{"header_rows":a,"stub_columns":b,"probability":float(p)} for (a,b,_),p in sorted(zip(candidates,probs),key=lambda z:z[1],reverse=True)[:10]]

    def _value_kind(self,value):
        text=self._clean(value)
        if not text:return "EMPTY"
        if self.PERIOD_RX.fullmatch(text):return "PERIOD"
        return "NUMBER" if self._numeric(text) is not None else "TEXT"

    def _content_type(self,text):
        s=self._clean(text)
        if not s:return "EMPTY"
        if s in {"-","–","—","N/A","해당없음"}:return "MISSING"
        if self.PERIOD_RX.search(s):return "PERIOD"
        return "NUMBER" if self._numeric(s) is not None else "TEXT"

    def _cluster_edges(self,values,tol=1.6):
        out=[]
        for v in sorted(float(x) for x in values):
            if not out or abs(v-out[-1])>tol:out.append(v)
            else:out[-1]=(out[-1]+v)/2
        return out

    def _restore_merge_spans(self,t):
        geoms=t.get("cell_geometry") or [];rows=t["row_count"];cols=t["column_count"]
        if not geoms or not rows or not cols:return []
        xs=self._cluster_edges([t["bbox"][0],t["bbox"][2]]+[z for g in geoms for z in (g["bbox"][0],g["bbox"][2])])
        ys=self._cluster_edges([t["bbox"][1],t["bbox"][3]]+[z for g in geoms for z in (g["bbox"][1],g["bbox"][3])])
        xcent=[(xs[i]+xs[i+1])/2 for i in range(len(xs)-1)];ycent=[(ys[i]+ys[i+1])/2 for i in range(len(ys)-1)];evidence=[]
        for g in geoms:
            b=g["bbox"];cc=[i for i,x in enumerate(xcent) if b[0]-1<=x<=b[2]+1];rr=[i for i,y in enumerate(ycent) if b[1]-1<=y<=b[3]+1]
            g["col_span"]=max(1,len(cc));g["row_span"]=max(1,len(rr))
            if g["col_span"]>1 or g["row_span"]>1:evidence.append({"row":g.get("row",0),"column":g.get("column",0),"row_span":g["row_span"],"col_span":g["col_span"],"bbox":g["bbox"]})
        return evidence

    def _stub_hierarchy(self,t,depth,stub,merges):
        sections=[]
        for e in merges:
            r=e["row"]
            if r>=depth and e["column"]==0 and e["col_span"]>=t["column_count"]:
                label=self._clean(t["matrix"][r][0]);sections.append({"row":r,"label":label,"role":"SECTION_STUB","level":0,"evidence":["FULL_ROW_MERGE"]})
        for i,x in enumerate(sections):x["child_row_start"]=x["row"]+1;x["child_row_end"]=(sections[i+1]["row"]-1 if i+1<len(sections) else t["row_count"]-1)
        return sections

    def _infer_roles(self,t,model):
        m=t["matrix"]
        if not m:return
        merges=self._restore_merge_spans(t);depth,stub,confidence,ranking=self._predict_boundaries(m,model)
        if not (0<=depth<t["row_count"] and 1<=stub<t["column_count"]):raise AssertionError("VALUE_RECTANGLE_REQUIRED")
        roles=[]
        for r,row in enumerate(m):
            for c,text in enumerate(row):
                region="HEADER_REGION" if r<depth else "ROW_DIMENSION_REGION" if c<stub else "DATA_REGION"
                roles.append({"row":r,"column":c,"text":text,"region_role":region,"role":region,"content_type":self._content_type(text)})
        t.update({"header_depth":depth,"stub_column_count":stub,"measure_start_column":stub,"joint_candidate_ranking":ranking,
                  "merge_evidence":merges,"boundary_confidence":confidence,"boundary_evidence":["JOINT_RECTANGULAR_ML","STRUCTURAL_FEATURES_ONLY","VALUE_RECTANGLE_CONSTRAINT"],
                  "cell_roles":roles,"stub_hierarchy":self._stub_hierarchy(t,depth,stub,merges),"status":"CONFIRMED" if confidence>=.75 else "REVIEW_REQUIRED",
                  "region_contract":{"spatial_roles":["HEADER_REGION","ROW_DIMENSION_REGION","DATA_REGION"],"rectangular_only":True,"header_optional":True,"value_rectangle_required":True,"postprocess_scope":"STUB_HIERARCHY_ONLY"}})

    def _assign_prediction(self,t,depth,stub,confidence,ranking,logical_meta):
        merges=self._restore_merge_spans(t);roles=[]
        if t["column_count"]>1 and not (0<=depth<=t["row_count"] and 1<=stub<t["column_count"]):
            raise AssertionError("PHYSICAL_MAPPING_INVALID")
        for r,row in enumerate(t["matrix"]):
            for c,text in enumerate(row):
                region="HEADER_REGION" if r<depth else "ROW_DIMENSION_REGION" if c<stub else "DATA_REGION"
                roles.append({"row":r,"column":c,"text":text,"region_role":region,"role":region,"content_type":self._content_type(text)})
        # A header-only physical segment is valid only because its logical table
        # has a positive value rectangle in a later segment.
        local_value_rows=t["row_count"]-depth
        t.update({"header_depth":depth,"stub_column_count":stub,"measure_start_column":stub,
                  "joint_candidate_ranking":ranking,"merge_evidence":merges,"boundary_confidence":confidence,
                  "boundary_evidence":["LOGICAL_TABLE_JOINT_ML","STRUCTURAL_FEATURES_ONLY","LOGICAL_VALUE_RECTANGLE_CONSTRAINT"],
                  "cell_roles":roles,"stub_hierarchy":self._stub_hierarchy(t,depth,stub,merges),
                  "status":"CONFIRMED" if confidence>=.75 else "REVIEW_REQUIRED","logical_region_prediction":logical_meta,
                  "local_value_rectangle_present":bool(local_value_rows>0 and t["column_count"]-stub>0),
                  "region_contract":{"spatial_roles":["HEADER_REGION","ROW_DIMENSION_REGION","DATA_REGION"],"rectangular_only":True,
                    "header_optional":True,"physical_header_only_segment_allowed":True,"logical_value_rectangle_required":True,"postprocess_scope":"STUB_HIERARCHY_ONLY"}})

    def _infer_logical_roles(self,tables,links,model):
        groups=defaultdict(list)
        for t in tables:groups[t["logical_table_id"]].append(t)
        out=[]
        confirmed={(x["from"],x["to"]) for x in links if x["status"]=="CONFIRMED"}
        for lid,segments in groups.items():
            segments.sort(key=lambda x:(x["page"],x["bbox"][1]))
            cols={x["column_count"] for x in segments};rows=sum(x["row_count"] for x in segments)
            connected=len(segments)>1 and all((segments[i]["table_id"],segments[i+1]["table_id"]) in confirmed for i in range(len(segments)-1))
            if len(segments)==1 and len(cols)==1 and next(iter(cols),0)>1:
                seg=segments[0];merges=self._restore_merge_spans(seg)
                h,s,conf,ranking=self._predict_boundaries(seg["matrix"],model,merges)
                meta={"logical_table_id":lid,"status":"PREDICTED_ON_LOGICAL_MATRIX","logical_shape":[seg["row_count"],seg["column_count"]],
                      "header_rows":h,"stub_columns":s,"value_shape":[seg["row_count"]-h,seg["column_count"]-s],"segment_count":1}
                self._assign_prediction(seg,h,s,conf,ranking,{**meta,"row_offset":0,"local_header_rows":h});out.append(meta)
            elif connected and len(cols)==1 and next(iter(cols),0)>1:
                # Deterministic continuity has already fixed the membership of
                # the logical table.  ML therefore solves one constrained
                # arrangement problem: every segment owns its own optional
                # HEADER rectangle, while all segments share one separator
                # boundary.  Select that boundary from the joint likelihood,
                # not from a mode/majority vote of independently predicted
                # stubs.  This is invariant to physical page coordinates.
                per_segment_stub_predictions=[]
                pi0=float(model.get("header_zero_rate",.01));strength=.25
                base_penalty=min(1.25,strength*np.log(max(1e-6,(1-pi0)/max(1e-6,pi0))))
                for index,seg in enumerate(segments):
                    merges=self._restore_merge_spans(seg)
                    candidates=self._candidate_rows(seg["matrix"],merges,allow_full_header=True)
                    probabilities=model["joint_model"].predict_proba([x[2] for x in candidates])[:,1]
                    scores=np.asarray([np.log(max(1e-9,p)/max(1e-9,1-p))-base_penalty*int(c[0]==0 and index==0) for c,p in zip(candidates,probabilities)])
                    choices={}
                    for candidate_stub in range(1,next(iter(cols))):
                        indices=[i for i,c in enumerate(candidates) if c[1]==candidate_stub]
                        ranked=sorted(indices,key=lambda i:probabilities[i],reverse=True)[:10]
                        ranking=[{"header_rows":candidates[i][0],"stub_columns":candidates[i][1],"probability":float(probabilities[i])} for i in ranked]
                        def packed(i):
                            h,s=candidates[i][:2]
                            return (h,s,float(probabilities[i]),ranking,float(scores[i]))
                        chosen=max(indices,key=lambda i:scores[i])
                        body_indices=[i for i in indices if candidates[i][0]<seg["row_count"]]
                        chosen_body=max(body_indices,key=lambda i:scores[i])
                        choices[candidate_stub]={"best":packed(chosen),"best_body":packed(chosen_body)}
                    per_segment_stub_predictions.append(choices)
                stub_trials=[]
                for candidate_stub in range(1,next(iter(cols))):
                    selected=[per_segment_stub_predictions[index][candidate_stub]["best"] for index in range(len(segments))]
                    joint_log_odds=sum(pred[4] for pred in selected)
                    if sum(seg["row_count"]-selected[index][0] for index,seg in enumerate(segments))<=0:
                        alternatives=[]
                        for index in range(len(segments)):
                            body=per_segment_stub_predictions[index][candidate_stub]["best_body"]
                            alternatives.append((body[4]-selected[index][4],index,body))
                        delta,index,body=max(alternatives,key=lambda x:x[0]);selected[index]=body;joint_log_odds+=delta
                    candidate_predictions=[pred[:4] for pred in selected]
                    stub_trials.append((joint_log_odds,candidate_stub,candidate_predictions))
                joint_score,common_stub,predictions=max(stub_trials,key=lambda x:x[0])
                header_rows=[x[0] for x in predictions];value_rows=sum(seg["row_count"]-predictions[i][0] for i,seg in enumerate(segments))
                meta={"logical_table_id":lid,"status":"PREDICTED_SEGMENT_RECTANGLES_ON_CONFIRMED_LOGICAL_TABLE",
                      "logical_shape":[rows,next(iter(cols))],"header_rows_by_segment":header_rows,"stub_columns":common_stub,
                      "value_shape":[value_rows,next(iter(cols))-common_stub],"segment_count":len(segments),"shared_stub_enforced":True,
                      "shared_stub_selection":"MAXIMUM_JOINT_ML_LOG_ODDS","shared_stub_joint_score":joint_score}
                for index,seg in enumerate(segments):
                    h,s,conf,ranking=predictions[index]
                    self._assign_prediction(seg,h,s,conf,ranking,{**meta,"segment_index":index,"local_header_rows":h})
                out.append(meta)
            elif connected and len(segments)==2 and segments[0]["row_count"]<=2 and segments[1]["column_count"]>segments[0]["column_count"]:
                a,b=segments;ac=[g for g in a.get("cell_geometry",[]) if g.get("row")==0];bc=[g for g in b.get("cell_geometry",[]) if g.get("row")==0]
                centers=[]
                self._restore_merge_spans(b)
                for g in bc:
                    span=max(1,int(g.get("col_span",1)));x0,x1=g["bbox"][0],g["bbox"][2]
                    for k in range(span):centers.append((int(g.get("column",0))+k,x0+(x1-x0)*(k+.5)/span))
                mapping=[]
                for p in sorted(ac,key=lambda x:x.get("column",0)):
                    kids=[c for c,x in centers if p["bbox"][0]-1<=x<=p["bbox"][2]+1];mapping.append(kids)
                if mapping and all(mapping) and sum(len(x) for x in mapping)==b["column_count"]:
                    h,s,conf,ranking=self._predict_boundaries(b["matrix"],model,self._restore_merge_spans(b))
                    meta={"logical_table_id":lid,"status":"PARENT_CHILD_COLUMN_MAPPING","parent_child_counts":[len(x) for x in mapping],"header_rows_by_segment":[a["row_count"],h],"stub_columns":s,"value_shape":[b["row_count"]-h,b["column_count"]-s],"segment_count":2}
                    self._assign_prediction(a,a["row_count"],min(s,a["column_count"]-1),conf,ranking,{**meta,"physical_role":"PARENT_HEADER"})
                    self._assign_prediction(b,h,s,conf,ranking,{**meta,"physical_role":"CHILD_HEADER_AND_BODY"});out.append(meta);continue
                reason="PARENT_CHILD_MAPPING_FAILED"
                audit={"logical_table_id":lid,"status":reason,"segment_count":2,"column_counts":sorted(cols)}
                for seg in segments:
                    h,s,conf,ranking=self._predict_boundaries(seg["matrix"],model,self._restore_merge_spans(seg));self._assign_prediction(seg,h,s,conf,ranking,{**audit,"fallback":"PHYSICAL_ML_REVIEW_REQUIRED"});seg["status"]="REVIEW_REQUIRED"
                out.append(audit)
            else:
                # Geometry mismatch cannot be silently padded because that
                # would invent logical columns. Each segment remains auditable.
                reason="UNSUPPORTED_COLUMN_GEOMETRY" if len(cols)>1 else "UNCONFIRMED_CHAIN"
                audit={"logical_table_id":lid,"status":reason,"segment_count":len(segments),"column_counts":sorted(cols)}
                for seg in segments:
                    h,s,conf,ranking=self._predict_boundaries(seg["matrix"],model,self._restore_merge_spans(seg))
                    self._assign_prediction(seg,h,s,conf,ranking,{**audit,"fallback":"PHYSICAL_ML_REVIEW_REQUIRED"})
                    seg["status"]="REVIEW_REQUIRED"
                out.append(audit)
        return out

    def _near_blocks(self,t,above=True,margin=75):
        y=t["bbox"][1] if above else t["bbox"][3]; out=[]
        for b in self.pages[t["page"]]["blocks"]:
            if above and 0<=y-b["bbox"][3]<=margin:out.append((y-b["bbox"][3],b))
            if not above and 0<=b["bbox"][1]-y<=margin:out.append((b["bbox"][1]-y,b))
        return [b for _,b in sorted(out,key=lambda x:x[0])]

    def _apply_continuation_semantics(self,tables,links):
        byid={t["table_id"]:t for t in tables}
        for l in links:
            if l["status"]!="CONFIRMED":continue
            a,b=byid[l["from"]],byid[l["to"]]
            if l.get("link_type") in {"HEADER_BODY_CONTINUATION","EXPANDED_HEADER_CONTINUATION"}:
                b["inherited_header"]={"source_table_id":a["table_id"],"source_page":a["page"],"matrix":a["matrix"],"status":"DETERMINISTIC_CONTINUATION_CONTEXT"}
                b["logical_header_source_table_id"]=a["table_id"]
                a["logical_header_target_table_id"]=b["table_id"]

    def _link_logical_context(self,tables):
        groups=defaultdict(list)
        for t in tables:groups[t["logical_table_id"]].append(t)
        for logical_id,segments in groups.items():
            segments.sort(key=lambda x:(x["page"],x["bbox"][1]))
            titles=[];units=[];notes=[]
            for t in segments:
                if t.get("title"):titles.append({**t["title"],"semantic_role":"TABLE_TITLE","source_table_id":t["table_id"]})
                units.extend({**u,"semantic_role":"UNIT","source_table_id":t["table_id"]} for u in t.get("units",[]) if u.get("bbox"))
                notes.extend({**n,"semantic_role":"TABLE_NOTE","source_table_id":t["table_id"]} for n in t.get("notes",[]))
            context={"logical_table_id":logical_id,"titles":titles,"units":units,"notes":notes}
            for t in segments:t["logical_context"]=context

    def _attach_context(self,tables):
        for t in tables:
            above=self._near_blocks(t,True); below=self._near_blocks(t,False)
            units=[b for b in above+below if self.UNIT_RX.search(b["text"])]
            periods=[b for b in above if self.PERIOD_RX.search(b["text"])]
            notes=[b for b in below if self.NOTE_RX.search(self._clean(b["text"]))]
            title=next((b for b in above if b not in units and b not in periods and len(self._clean(b["text"]))<=140),None)
            t["title"]={"text":title["text"],"page":title["page"],"bbox":title["bbox"]} if title else None
            t["units"]=[{"text":b["text"],"page":b["page"],"bbox":b["bbox"],"assignment_source":"EXPLICIT","confidence":.96} for b in units]
            t["period_context"]=[{"text":b["text"],"page":b["page"],"bbox":b["bbox"]} for b in periods]
            t["notes"]=[{"text":b["text"],"page":b["page"],"bbox":b["bbox"]} for b in notes]

    def _inherit_units(self,tables,links):
        byid={t["table_id"]:t for t in tables}
        for l in links:
            a,b=byid[l["from"]],byid[l["to"]]
            if not b["units"] and a["units"] and l["status"]=="CONFIRMED":
                b["units"]=[{**u,"assignment_source":"INHERITED","source_table_id":a["table_id"],"confidence":round(l["score"]*.95,3)} for u in a["units"]]
        previous=None
        for t in sorted(tables,key=lambda x:(x["page"],x["bbox"][1])):
            if not t["units"] and previous and previous["column_count"]==t["column_count"] and previous["units"]:
                t["units"]=[{**u,"assignment_source":"INHERITED","source_table_id":previous["table_id"],"confidence":.62} for u in previous["units"]]
            if not t["units"]:t["units"]=[{"text":"UNKNOWN","assignment_source":"UNKNOWN","confidence":0.0}]
            previous=t

    def _numbering_level(self,text):
        s=self._clean(text)
        patterns=[
            (0,r"^(?:제\s*\d+\s*[편장]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+[.．]|[A-Z][.．])"),
            (1,r"^(?:\d+[.．](?!\d)|[가-힣][.．])"),
            (2,r"^(?:\d+[.)]|[(（]\d+[)）])"),
            (3,r"^(?:[①②③④⑤⑥⑦⑧⑨⑩]|[(（][가-힣][)）])"),
        ]
        for level,pat in patterns:
            if re.match(pat,s):return level
        return None

    HIERARCHY_PATTERNS=[
        ("ROMAN",0,re.compile(r"^\s*(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+|[IVXLCDM]+)[.．]\s*\S+")),
        ("ARABIC_DOT",1,re.compile(r"^\s*\d{1,3}[.．](?!\d)\s*\S+")),
        ("KOREAN_DOT",2,re.compile(r"^\s*[가-힣][.．]\s*\S+")),
        ("COMPOUND_NUMBER",2,re.compile(r"^\s*\d+(?:-\d+)+[.)．]?\s*\S+")),
        ("ARABIC_PAREN",3,re.compile(r"^\s*[(（]\d+[)）]\s*\S+")),
        ("ARABIC_RPAREN",3,re.compile(r"^\s*\d+[)）]\s*\S+")),
        ("KOREAN_PAREN",3,re.compile(r"^\s*[(（][가-힣][)）]\s*\S+")),
        ("CIRCLED",3,re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨⑩]\s*\S+")),
        ("BRACKET",0,re.compile(r"^\s*[【\[].+?[】\]]\s*$")),
    ]

    def _line_objects(self):
        out=[]
        for p in self.raw["pages"]:
            for b in p["blocks"]:
                for li,line in enumerate(b.get("lines") or []):
                    text=self._clean("".join(s.get("text","") for s in line.get("spans",[])))
                    if text:out.append({"element_id":f"{b['element_id']}_L{li:03d}","page":p["page"],"bbox":line["bbox"],"text":text,
                      "font_size_max":max((s.get("size",0) for s in line.get("spans",[])),default=0),"reading_order":b["reading_order"]*100+li})
        return out

    def _hierarchy_family(self,text):
        for family,level,rx in self.HIERARCHY_PATTERNS:
            if rx.match(text):return family,level
        return None,None

    def _document_regions(self,tables):
        table_boxes=defaultdict(list)
        for t in tables:table_boxes[t["page"]].append(fitz.Rect(t["bbox"]))
        lines=self._line_objects(); heads=[]; body=[]; furniture=[]
        for x in lines:
            rect=fitz.Rect(x["bbox"])
            if any(rect.intersects(tb) for tb in table_boxes[x["page"]]):continue
            page_h=self.pages[x["page"]]["height"]
            if rect.y0<24 or rect.y1>page_h-24:furniture.append(x);continue
            family,level=self._hierarchy_family(x["text"])
            prose=len(x["text"])>=90 or bool(re.search(r"(?:다|함|음)[.。]?$",x["text"]))
            numeric_only=not bool(re.search(r"[가-힣A-Za-z]",x["text"]))
            if family and not prose and not numeric_only:
                heads.append({**x,"family":family,"level":level,"raw_level":level,"semantic_role":"SECTION_HEADING"})
            else:body.append(x)
        heads.sort(key=lambda x:(x["page"],x["bbox"][1],x["bbox"][0])); stack=[]; locked=[]
        for h in heads:
            level=int(h["level"])
            while stack and int(stack[-1]["level"])>=level:stack.pop()
            h["parent_id"]=stack[-1]["element_id"] if stack else None; h["hierarchy_locked"]=True
            locked.append(h);stack.append(h)
        # Scope assignment occurs only after hierarchy is locked.
        for x in body:
            prior=[h for h in locked if (h["page"],h["bbox"][1],h["bbox"][0]) < (x["page"],x["bbox"][1],x["bbox"][0])]
            x["scope_heading_id"]=prior[-1]["element_id"] if prior else None
        return locked,furniture,body


    def _annotation(self,tables,heads,furn,body,links):
        ann={"headings":[],"hierarchy_rails":[],"page_furniture":[],"body_text":[],
             "tables":[],"logical_table_contexts":[],"cells":[],"continuity_links":links}
        ordered=sorted(heads,key=lambda h:(h["page"],h["bbox"][1],h["bbox"][0]))
        for i,h in enumerate(ordered):
            ann["headings"].append({"object_id":h["element_id"],"page":h["page"],"bbox":h["bbox"],"text":h.get("text"),"family":h.get("family"),"level":h["level"],"parent_id":h.get("parent_id"),"hierarchy_locked":h.get("hierarchy_locked",False)})
            terminal=next((n for n in ordered[i+1:] if int(n["level"])<=int(h["level"])),None)
            end_page=terminal["page"] if terminal else self.raw["page_count"]
            for page in range(h["page"],end_page+1):
                page_h=self.pages[page]["height"]
                y0=h["bbox"][1] if page==h["page"] else 24
                y1=(terminal["bbox"][1]-2 if terminal and page==terminal["page"] else page_h-24)
                if y1<=y0:continue
                ann["hierarchy_rails"].append({"object_id":h["element_id"],"page":page,"level":h["level"],
                    "y0":y0,"y1":y1,"heading_bbox":h["bbox"] if page==h["page"] else None,
                    "start_hook":page==h["page"],"continued":page>h["page"],"terminal_heading_id":terminal["element_id"] if terminal else None})
        ann["page_furniture"]=[{"page":x["page"],"bbox":x["bbox"]} for x in furn]
        ann["body_text"]=[{"object_id":x.get("element_id"),"page":x["page"],"bbox":x["bbox"],"text":x.get("text"),"scope_heading_id":x.get("scope_heading_id")} for x in body]
        seen_context=set()
        for t in tables:
            prior=[h for h in ordered if (h["page"],h["bbox"][1],h["bbox"][0])<(t["page"],t["bbox"][1],t["bbox"][0])]
            t["scope_heading_id"]=prior[-1]["element_id"] if prior else None
            ann["tables"].append({"page":t["page"],"object_id":t["table_id"],"logical_table_id":t["logical_table_id"],
                "bbox":t["bbox"],"status":t["status"],"title":t["title"],"scope_heading_id":t["scope_heading_id"],
                "row_count":t["row_count"],"column_count":t["column_count"],"header_depth":t["header_depth"],"stub_column_count":t["stub_column_count"],
                "inherited_header":t.get("inherited_header"),"logical_header_source_table_id":t.get("logical_header_source_table_id"),
                "units":[u for u in t["units"] if u.get("bbox")],"notes":t["notes"]})
            ctx=t.get("logical_context",{})
            if t["logical_table_id"] not in seen_context:
                ann["logical_table_contexts"].append(ctx);seen_context.add(t["logical_table_id"])
            for g in t["cell_geometry"]:
                r,c=g.get("row",0),g.get("column",0)
                role=next((x["role"] for x in t["cell_roles"] if x["row"]==r and x["column"]==c),"EMPTY")
                ann["cells"].append({"page":t["page"],"table_id":t["table_id"],"bbox":g["bbox"],"row":r,"column":c,"visual_role":role})
        ann["annotation_source"]="SEMANTIC_PROMPT_TRANSFER_V0.14_LOGICAL_SCOPE_AND_CONTINUATION"
        return ann
