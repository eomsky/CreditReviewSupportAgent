from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict

import numpy as np


DATE_RX_V015 = re.compile(
    r"^(?:(?:19|20)\d{2}[-./]\d{1,2}[-./]\d{1,2}|"
    r"(?:19|20)\d{2}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일)$"
)


def install_v015_builder(base_class):
    """Return the v0.15 builder subclass for a loaded v0.14 runtime."""

    class DocumentBuilderV015(base_class):
        OUTER_TOL = 0.015
        STUB_TOL = 0.012
        EDGE_TOL = 0.012

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._v015_refined_fingerprints = set()
            self._v015_rule_audit = Counter()

        def _value_kind_v015(self, value):
            text = self._clean(value)
            if not text:
                return "EMPTY"
            if text in {"-", "–", "—", "N/A", "해당없음"}:
                return "MISSING"
            if DATE_RX_V015.fullmatch(text):
                return "DATE"
            if self._numeric(text) is not None:
                return "NUMBER"
            return "TEXT"

        @staticmethod
        def _covered_cells_v015(merges):
            covered = set()
            for merge in merges or []:
                row = int(merge["row"])
                column = int(merge["column"])
                for rr in range(row, row + int(merge["row_span"])):
                    for cc in range(column, column + int(merge["col_span"])):
                        if (rr, cc) != (row, column):
                            covered.add((rr, cc))
            return covered

        @staticmethod
        def _matrix_fingerprint_v015(matrix):
            payload = json.dumps(matrix, ensure_ascii=False, separators=(",", ":"))
            return hashlib.sha1(payload.encode("utf-8")).hexdigest()

        def _refined_body_boundary_v015(self, matrix, merges, h, s):
            rows = len(matrix)
            columns = len(matrix[0]) if matrix else 0
            if h <= 1 or rows < 2 or not (1 <= s < columns):
                return False
            covered = self._covered_cells_v015(merges)
            row0, row1 = matrix[0], matrix[1]
            true_blanks = [
                c
                for c in range(columns)
                if not self._clean(row0[c]) and (0, c) not in covered
            ]
            if not any(self._clean(row1[c]) for c in true_blanks):
                return False
            if not any(self._clean(row0[c]) for c in range(s, columns)):
                return False
            if not any(self._value_kind_v015(row1[c]) == "TEXT" for c in range(s)):
                return False

            value_kinds = [self._value_kind_v015(row1[c]) for c in range(s, columns)]
            typed_values = sum(kind in {"DATE", "NUMBER", "MISSING"} for kind in value_kinds)
            nonempty_values = sum(kind != "EMPTY" for kind in value_kinds)
            parent_spans = [
                merge
                for merge in merges or []
                if int(merge["row"]) == 0 and int(merge["col_span"]) > 1
            ]
            child_expansion = bool(
                parent_spans
                and nonempty_values >= 2
                and all(
                    kind in {"TEXT", "DATE"}
                    for kind in value_kinds
                    if kind != "EMPTY"
                )
            )
            if child_expansion or typed_values > 1:
                return False

            lookahead_support = False
            if rows >= 3:
                row2 = matrix[2]
                row2_label = any(
                    self._value_kind_v015(row2[c]) == "TEXT" for c in range(s)
                )
                row2_kinds = [
                    self._value_kind_v015(row2[c]) for c in range(s, columns)
                ]
                row2_typed = sum(
                    kind in {"DATE", "NUMBER", "MISSING"} for kind in row2_kinds
                )
                row2_nonempty = sum(kind != "EMPTY" for kind in row2_kinds)
                lookahead_support = (
                    row2_label
                    and row2_typed >= 1
                    and row2_typed == row2_nonempty
                )
            return typed_values == 1 or (nonempty_values == 0 and lookahead_support)

        def _predict_boundaries(
            self, matrix, bundle, merges=None, allow_headerless=False, fixed_stub=None
        ):
            h, s, confidence, ranking = super()._predict_boundaries(
                matrix,
                bundle,
                merges=merges,
                allow_headerless=allow_headerless,
                fixed_stub=fixed_stub,
            )
            if self._refined_body_boundary_v015(matrix, merges or [], h, s):
                candidate = next(
                    (
                        item
                        for item in ranking
                        if item["header_rows"] == 1 and item["stub_columns"] == s
                    ),
                    None,
                )
                if candidate is None:
                    candidates = self._candidate_rows(matrix, merges)
                    candidates = [item for item in candidates if item[0] == 1 and item[1] == s]
                    if candidates:
                        probability = float(
                            bundle["joint_model"].predict_proba([candidates[0][2]])[0, 1]
                        )
                        candidate = {
                            "header_rows": 1,
                            "stub_columns": s,
                            "probability": probability,
                        }
                        ranking = sorted(
                            [*ranking, candidate],
                            key=lambda item: item["probability"],
                            reverse=True,
                        )[:10]
                if candidate is not None:
                    self._v015_refined_fingerprints.add(
                        self._matrix_fingerprint_v015(matrix)
                    )
                    return 1, s, float(candidate["probability"]), ranking
            return h, s, confidence, ranking

        @staticmethod
        def _norm_x_v015(table, x):
            x0, _, x1, _ = table["bbox"]
            return (float(x) - float(x0)) / max(1.0, float(x1) - float(x0))

        def _outer_alignment_v015(self, a, b):
            left_a = a["bbox"][0] / max(1.0, a["page_width"])
            left_b = b["bbox"][0] / max(1.0, b["page_width"])
            right_a = a["bbox"][2] / max(1.0, a["page_width"])
            right_b = b["bbox"][2] / max(1.0, b["page_width"])
            return (
                abs(left_a - left_b) <= self.OUTER_TOL
                and abs(right_a - right_b) <= self.OUTER_TOL
            )

        def _stub_boundary_v015(self, table):
            rights = [
                self._norm_x_v015(table, geometry["bbox"][2])
                for geometry in table.get("cell_geometry", [])
                if int(geometry.get("column", -1)) == 0
            ]
            rights = [value for value in rights if 0.02 < value < 0.9]
            if not rights:
                return None
            return float(max(rights))

        def _matching_stub_boundary_v015(self, a, b):
            """Resolve one shared separator from geometric edges only.

            A header-only predecessor may expose several blank stub cells, so
            its physical column-0 right edge is not necessarily the logical
            separator.  Prefer the successor's widest row-dimension span and
            require that exact normalized edge to exist in the predecessor.
            """
            edges_a = self._atomic_edges_v015(a)
            edges_b = self._atomic_edges_v015(b)
            preferred_b = self._stub_boundary_v015(b)
            if preferred_b is not None and any(
                abs(edge - preferred_b) <= self.STUB_TOL for edge in edges_a
            ):
                return preferred_b
            preferred_a = self._stub_boundary_v015(a)
            if preferred_a is not None and any(
                abs(edge - preferred_a) <= self.STUB_TOL for edge in edges_b
            ):
                return preferred_a
            return None

        def _atomic_edges_v015(self, table):
            edges = {0.0, 1.0}
            for geometry in table.get("cell_geometry", []):
                edges.add(round(self._norm_x_v015(table, geometry["bbox"][0]), 4))
                edges.add(round(self._norm_x_v015(table, geometry["bbox"][2]), 4))
            return sorted(edges)

        def _row_intervals_v015(self, table, row):
            intervals = []
            for geometry in table.get("cell_geometry", []):
                if int(geometry.get("row", -1)) != row:
                    continue
                left = self._norm_x_v015(table, geometry["bbox"][0])
                right = self._norm_x_v015(table, geometry["bbox"][2])
                intervals.append((left, right, int(geometry.get("column", -1))))
            return sorted(intervals)

        def _parent_child_span_union_v015(self, a, b, stub_boundary=None):
            stub_boundary = (
                self._matching_stub_boundary_v015(a, b)
                if stub_boundary is None
                else stub_boundary
            )
            if stub_boundary is None:
                return None
            stub_a = stub_b = stub_boundary
            successor_edges = self._atomic_edges_v015(b)
            successor_measure_edges = [
                edge for edge in successor_edges if edge >= stub_b - self.EDGE_TOL
            ]
            if len(successor_measure_edges) < 2:
                return None

            candidates = []
            for row in range(a["row_count"]):
                intervals = [
                    (left, right, column)
                    for left, right, column in self._row_intervals_v015(a, row)
                    if right > stub_a + self.EDGE_TOL
                ]
                if not intervals:
                    continue
                intervals = [
                    (max(left, stub_a), right, column)
                    for left, right, column in intervals
                    if right - max(left, stub_a) > self.EDGE_TOL
                ]
                if not intervals:
                    continue
                if abs(intervals[0][0] - stub_a) > self.EDGE_TOL:
                    continue
                if abs(intervals[-1][1] - 1.0) > self.EDGE_TOL:
                    continue
                if any(
                    abs(intervals[index][1] - intervals[index + 1][0])
                    > self.EDGE_TOL
                    for index in range(len(intervals) - 1)
                ):
                    continue
                counts = []
                valid = True
                for left, right, _ in intervals:
                    left_matches = [
                        edge
                        for edge in successor_measure_edges
                        if abs(edge - left) <= self.EDGE_TOL
                    ]
                    right_matches = [
                        edge
                        for edge in successor_measure_edges
                        if abs(edge - right) <= self.EDGE_TOL
                    ]
                    if not left_matches or not right_matches:
                        valid = False
                        break
                    inside = [
                        edge
                        for edge in successor_measure_edges
                        if left - self.EDGE_TOL <= edge <= right + self.EDGE_TOL
                    ]
                    count = max(0, len(inside) - 1)
                    if count < 1:
                        valid = False
                        break
                    counts.append(count)
                if valid:
                    candidates.append((row, counts))
            if not candidates:
                return None
            row, counts = max(
                candidates,
                key=lambda item: (len(item[1]), max(item[1]), item[0]),
            )
            return {
                "predecessor_row": row,
                "successor_columns_per_parent": counts,
                "expanded": any(count > 1 for count in counts),
            }

        def _continuity_links(self, tables):
            by_page = defaultdict(list)
            for table in tables:
                by_page[table["page"]].append(table)
            links = []
            for page in sorted(by_page):
                if page + 1 not in by_page:
                    continue
                a = max(by_page[page], key=lambda table: table["bbox"][3])
                b = min(by_page[page + 1], key=lambda table: table["bbox"][1])
                page_boundary = (
                    b["page"] == a["page"] + 1
                    and a["bbox"][3] / a["page_height"] >= 0.82
                    and b["bbox"][1] / b["page_height"] <= 0.22
                )
                outer_width = self._outer_alignment_v015(a, b)
                shared_stub = self._matching_stub_boundary_v015(a, b)
                stub_boundary = shared_stub is not None
                mapping = (
                    self._parent_child_span_union_v015(a, b, shared_stub)
                    if stub_boundary
                    else None
                )
                if mapping is not None:
                    counts = mapping["successor_columns_per_parent"]
                    same_grid_union = (
                        a["column_count"] == b["column_count"]
                        and bool(counts)
                    )
                    expanded_union = (
                        b["column_count"] > a["column_count"]
                        and mapping["expanded"]
                        and len(counts) >= 2
                    )
                    if not (same_grid_union or expanded_union):
                        mapping = None
                span_union = mapping is not None
                conditions = {
                    "page_boundary": page_boundary,
                    "normalized_outer_width": outer_width,
                    "separator_stub_boundary": stub_boundary,
                    "parent_span_successor_union": span_union,
                }
                passed = sum(bool(value) for value in conditions.values())
                if passed < 2:
                    continue
                confirmed = passed == 4
                evidence = [
                    name.upper() for name, value in conditions.items() if value
                ]
                link_type = (
                    "STRUCTURAL_EXPANDED_HEADER_CONTINUATION"
                    if mapping and mapping["expanded"]
                    else "STRUCTURAL_GRID_CONTINUATION"
                )
                links.append(
                    {
                        "from": a["table_id"],
                        "to": b["table_id"],
                        "score": round(passed / 4.0, 4),
                        "evidence": evidence,
                        "status": "CONFIRMED" if confirmed else "REVIEW_REQUIRED",
                        "link_type": link_type,
                        "structural_conditions": conditions,
                        "parent_child_mapping": mapping,
                        "decision_feature_policy": "FOUR_STRUCTURAL_CONDITIONS_ONLY",
                    }
                )
            return links

        def _infer_logical_roles(self, tables, links, model):
            inference = super()._infer_logical_roles(tables, links, model)
            by_id = {table["table_id"]: table for table in tables}
            by_logical = {item.get("logical_table_id"): index for index, item in enumerate(inference)}
            for link in links:
                if link["status"] != "CONFIRMED":
                    continue
                a, b = by_id[link["from"]], by_id[link["to"]]
                mapping = link.get("parent_child_mapping")
                if not mapping or a["column_count"] == b["column_count"]:
                    continue
                predecessor_stub = 1
                confidence = float(b.get("boundary_confidence", 0.0))
                ranking = [
                    {
                        "header_rows": a["row_count"],
                        "stub_columns": predecessor_stub,
                        "probability": confidence,
                    }
                ]
                meta = {
                    "logical_table_id": a["logical_table_id"],
                    "status": "STRUCTURAL_PARENT_CHILD_MAPPING",
                    "header_rows_by_segment": [a["row_count"], b["header_depth"]],
                    "stub_columns_by_segment": [predecessor_stub, b["stub_column_count"]],
                    "segment_count": 2,
                    "parent_child_counts": mapping["successor_columns_per_parent"],
                    "mapping_source": "NORMALIZED_GEOMETRIC_SPAN_UNION",
                }
                self._assign_prediction(
                    a,
                    a["row_count"],
                    predecessor_stub,
                    confidence,
                    ranking,
                    {**meta, "physical_role": "PARENT_HEADER"},
                )
                a["status"] = "CONFIRMED"
                b["logical_region_prediction"] = {
                    **meta,
                    "physical_role": "CHILD_HEADER_AND_BODY",
                }
                index = by_logical.get(a["logical_table_id"])
                if index is not None:
                    inference[index] = meta
                else:
                    inference.append(meta)
                self._v015_rule_audit["expanded_continuation_repairs"] += 1

            for table in tables:
                fingerprint = self._matrix_fingerprint_v015(table["matrix"])
                if fingerprint in self._v015_refined_fingerprints:
                    table["boundary_evidence"] = list(
                        dict.fromkeys(
                            [
                                *table.get("boundary_evidence", []),
                                "V015_TRUE_BLANK_FILLED_BY_BODY_LABEL",
                                "V015_TYPED_VALUE_OR_TYPED_LOOKAHEAD",
                                "V015_PARENT_CHILD_HEADER_EXPANSION_REJECTED",
                                "V015_OOF_ZERO_REGRESSION_GATE",
                            ]
                        )
                    )
                    table["boundary_repair"] = "REFINED_TYPED_BODY_BOUNDARY"
                    self._v015_rule_audit["typed_body_boundary_repairs"] += 1

            family_groups = defaultdict(list)
            for table in tables:
                first_row = tuple(
                    self._clean(value)
                    for value in table["matrix"][0]
                    if self._clean(value)
                ) if table["matrix"] else ()
                edges = tuple(round(edge, 2) for edge in self._atomic_edges_v015(table))
                family_groups[(table["page"], table["column_count"], first_row, edges)].append(table)
            for family in family_groups.values():
                if len(family) < 2:
                    continue
                header_counts = Counter(table["header_depth"] for table in family)
                consensus, count = header_counts.most_common(1)[0]
                if count < 2:
                    continue
                for table in family:
                    if table["header_depth"] == consensus:
                        table["boundary_evidence"] = list(
                            dict.fromkeys(
                                [
                                    *table.get("boundary_evidence", []),
                                    "V015_LOCAL_STRUCTURAL_FAMILY_AGREEMENT",
                                ]
                            )
                        )
                        self._v015_rule_audit["family_agreement_corroborations"] += 1
            return inference

        def _apply_continuation_semantics(self, tables, links):
            super()._apply_continuation_semantics(tables, links)
            by_id = {table["table_id"]: table for table in tables}
            for link in links:
                if link["status"] != "CONFIRMED":
                    continue
                if not link.get("link_type", "").startswith("STRUCTURAL_"):
                    continue
                a, b = by_id[link["from"]], by_id[link["to"]]
                b["inherited_header"] = {
                    "source_table_id": a["table_id"],
                    "source_page": a["page"],
                    "matrix": a["matrix"],
                    "status": "STRUCTURAL_CONTINUATION_CONTEXT",
                }
                b["logical_header_source_table_id"] = a["table_id"]
                a["logical_header_target_table_id"] = b["table_id"]

        def build(self, raw):
            self._v015_refined_fingerprints.clear()
            self._v015_rule_audit.clear()
            result = super().build(raw)
            result["schema_version"] = "0.15"
            result["processing_policy"].update(
                {
                    "header_boundary_repair": "REFINED_TYPED_BODY_BOUNDARY",
                    "local_family_policy": "CORROBORATION_ONLY_UNLESS_ZERO_REGRESSION_PROVEN",
                    "continuation_decision": "FOUR_STRUCTURAL_CONDITIONS_ONLY",
                    "continuation_excluded_features": [
                        "UNIT",
                        "TITLE",
                        "PERIOD_TEXT",
                        "LEXICAL_MEANING",
                        "NUMERIC_RATIO",
                    ],
                    "unit_inheritance_order": "AFTER_CONFIRMED_LINK",
                }
            )
            result["v0.15_rule_audit"] = dict(self._v015_rule_audit)
            result["annotation"]["annotation_source"] = (
                "SEMANTIC_PROMPT_TRANSFER_V0.15_ZERO_REGRESSION_STRUCTURAL_RULES"
            )
            return result

    DocumentBuilderV015.__name__ = "DocumentBuilderV015"
    return DocumentBuilderV015
