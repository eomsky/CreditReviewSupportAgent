from __future__ import annotations

from collections import Counter, defaultdict


def install_v016_builder(base_class):
    """Return the v0.16 builder layered on the accepted v0.15 runtime."""

    class DocumentBuilderV016(base_class):
        TITLE_TABLE_OVERLAP_RATIO = 0.20
        NARRATIVE_LONG_TEXT = 24

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._v016_rule_audit = Counter()
            self._v016_filtered_block_keys = set()

        @staticmethod
        def _intersection_ratio_v016(inner_bbox, outer_bbox):
            ix0 = max(float(inner_bbox[0]), float(outer_bbox[0]))
            iy0 = max(float(inner_bbox[1]), float(outer_bbox[1]))
            ix1 = min(float(inner_bbox[2]), float(outer_bbox[2]))
            iy1 = min(float(inner_bbox[3]), float(outer_bbox[3]))
            intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
            area = max(1.0, float(inner_bbox[2]) - float(inner_bbox[0])) * max(
                1.0, float(inner_bbox[3]) - float(inner_bbox[1])
            )
            return intersection / area

        def _inside_physical_table_v016(self, block):
            bbox = block.get("bbox")
            if not bbox:
                return False
            center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
            center_y = (float(bbox[1]) + float(bbox[3])) / 2.0
            for table in self.raw.get("physical_tables", []):
                if int(table.get("page", -1)) != int(block.get("page", -2)):
                    continue
                table_bbox = table.get("bbox")
                if not table_bbox:
                    continue
                center_inside = (
                    float(table_bbox[0]) <= center_x <= float(table_bbox[2])
                    and float(table_bbox[1]) <= center_y <= float(table_bbox[3])
                )
                if center_inside or self._intersection_ratio_v016(
                    bbox, table_bbox
                ) >= self.TITLE_TABLE_OVERLAP_RATIO:
                    return True
            return False

        def _near_blocks(self, table, above=True, margin=75):
            candidates = super()._near_blocks(table, above=above, margin=margin)
            retained = []
            for block in candidates:
                if not self._inside_physical_table_v016(block):
                    retained.append(block)
                    continue
                key = (
                    int(block.get("page", -1)),
                    tuple(round(float(value), 2) for value in block.get("bbox", [])),
                    self._clean(block.get("text", "")),
                )
                if key not in self._v016_filtered_block_keys:
                    self._v016_filtered_block_keys.add(key)
                    self._v016_rule_audit["context_blocks_inside_tables_rejected"] += 1
            return retained

        def _header_like_value_v016(self, value):
            text = self._clean(value)
            if not text:
                return False
            compact = text.replace(" ", "")
            terms = [self._clean(term).replace(" ", "") for term in self.HEADER_TERMS]
            return len(compact) <= 20 and any(
                compact == term or compact.endswith(term) for term in terms
            )

        def _narrative_boundary_proposal_v016(self, table, current_h, current_s):
            """Find the first high-confidence label/value BODY row.

            The rule is deliberately narrow: it only shortens an over-deep
            low-confidence boundary, requires a repeated label/value grammar,
            and rejects ordinary short header labels and parent-child header
            expansion.
            """

            matrix = table.get("matrix") or []
            rows = len(matrix)
            columns = len(matrix[0]) if matrix else 0
            if current_h < 2 or rows < 2 or columns < 2:
                return None
            merges = self._restore_merge_spans(table)
            proposals = []
            for stub in range(1, columns):
                for row_index in range(min(current_h, rows)):
                    row = matrix[row_index]
                    labels = [self._clean(row[column]) for column in range(stub)]
                    values = [
                        self._clean(row[column]) for column in range(stub, columns)
                    ]
                    labels = [value for value in labels if value]
                    values = [value for value in values if value]
                    if not labels or not values:
                        continue
                    if all(self._header_like_value_v016(value) for value in values):
                        continue
                    parent_spans = [
                        merge
                        for merge in merges or []
                        if int(merge.get("row", -1)) == row_index
                        and int(merge.get("col_span", 1)) > 1
                        and not (
                            int(merge.get("column", -1)) < stub
                            and int(merge.get("column", -1))
                            + int(merge.get("col_span", 1))
                            <= stub
                        )
                    ]
                    if parent_spans:
                        continue

                    support = 0
                    typed_or_long = 0
                    current_typed_or_long = 0
                    for lookahead in range(row_index, min(rows, row_index + 3)):
                        candidate = matrix[lookahead]
                        left_nonempty = any(
                            self._clean(candidate[column]) for column in range(stub)
                        )
                        right_values = [
                            self._clean(candidate[column])
                            for column in range(stub, columns)
                            if self._clean(candidate[column])
                        ]
                        if right_values and (left_nonempty or lookahead > row_index):
                            support += 1
                        for value in right_values:
                            kind = self._value_kind_v015(value)
                            if kind in {"DATE", "NUMBER", "MISSING"} or len(value) >= self.NARRATIVE_LONG_TEXT:
                                typed_or_long += 1
                                if lookahead == row_index:
                                    current_typed_or_long += 1
                    if support < 2 or typed_or_long < 1:
                        continue
                    horizontal_merges_before_body = [
                        merge
                        for merge in merges or []
                        if int(merge.get("row", -1)) < row_index
                        and int(merge.get("col_span", 1)) > 1
                    ]
                    two_column_attribute_run = (
                        columns == 2
                        and support >= 3
                        and not horizontal_merges_before_body
                    )
                    sparse_banner_then_value = False
                    if row_index == 1:
                        prefix = matrix[0]
                        prefix_left = any(
                            self._clean(prefix[column]) for column in range(stub)
                        )
                        prefix_right = sum(
                            bool(self._clean(prefix[column]))
                            for column in range(stub, columns)
                        )
                        sparse_banner_then_value = (
                            not prefix_left
                            and prefix_right == 1
                            and typed_or_long > current_typed_or_long
                        )
                    if not (
                        current_typed_or_long
                        or two_column_attribute_run
                        or sparse_banner_then_value
                    ):
                        continue
                    proposals.append(
                        {
                            "header_rows": row_index,
                            "stub_columns": stub,
                            "support_rows": support,
                            "typed_or_long_values": typed_or_long,
                            "keeps_current_stub": stub == current_s,
                        }
                    )
                    break
            if not proposals:
                return None
            return min(
                proposals,
                key=lambda item: (
                    item["header_rows"],
                    not item["keeps_current_stub"],
                    -item["support_rows"],
                    -item["typed_or_long_values"],
                ),
            )

        def _candidate_probability_v016(self, table, model, header_rows, stub_columns):
            merges = self._restore_merge_spans(table)
            candidates = self._candidate_rows(
                table["matrix"], merges, allow_full_header=True
            )
            selected = next(
                (
                    candidate
                    for candidate in candidates
                    if int(candidate[0]) == int(header_rows)
                    and int(candidate[1]) == int(stub_columns)
                ),
                None,
            )
            if selected is None:
                return 0.0, table.get("joint_candidate_ranking", [])
            probability = float(
                model["joint_model"].predict_proba([selected[2]])[0, 1]
            )
            ranking = list(table.get("joint_candidate_ranking", []))
            candidate_row = {
                "header_rows": int(header_rows),
                "stub_columns": int(stub_columns),
                "probability": probability,
            }
            if not any(
                int(item["header_rows"]) == int(header_rows)
                and int(item["stub_columns"]) == int(stub_columns)
                for item in ranking
            ):
                ranking.append(candidate_row)
                ranking = sorted(
                    ranking, key=lambda item: item["probability"], reverse=True
                )[:10]
            return probability, ranking

        @staticmethod
        def _same_text_v016(left, right):
            normalize = lambda value: "".join(str(value or "").split()).lower()
            return bool(normalize(left)) and normalize(left) == normalize(right)

        def _repeated_header_depth_v016(self, source, successor):
            source_rows = source.get("matrix", [])[: int(source.get("header_depth", 0))]
            if not source_rows or not successor.get("matrix"):
                return 0
            repeated = 0
            for index, source_row in enumerate(source_rows):
                if index >= successor["row_count"]:
                    break
                successor_row = successor["matrix"][index]
                source_nonempty = [
                    column
                    for column, value in enumerate(source_row)
                    if self._clean(value)
                ]
                if not source_nonempty:
                    break
                matches = sum(
                    column < len(successor_row)
                    and self._same_text_v016(
                        source_row[column], successor_row[column]
                    )
                    for column in source_nonempty
                )
                required = 1 if len(source_nonempty) == 1 else 2
                if matches < required or matches / len(source_nonempty) < 0.60:
                    break
                repeated += 1
            return repeated

        def _continued_row_refinement_v016(self, a, b, mapping):
            if not mapping:
                return False
            if not (
                a["column_count"] == 2
                and b["column_count"] > a["column_count"]
                and a["row_count"] == 1
            ):
                return False
            counts = mapping.get("successor_columns_per_parent") or []
            if counts != [b["column_count"] - 1]:
                return False
            predecessor_row = a["matrix"][-1]
            successor_row = b["matrix"][0]
            if not self._clean(predecessor_row[0]) or self._clean(successor_row[0]):
                return False
            successor_intervals = [
                interval
                for interval in self._row_intervals_v015(b, 0)
                if interval[1] > self._matching_stub_boundary_v015(a, b) + self.EDGE_TOL
            ]
            if len(successor_intervals) != 1:
                return False
            refined_rows = []
            for row_index in range(1, b["row_count"]):
                intervals = [
                    interval
                    for interval in self._row_intervals_v015(b, row_index)
                    if interval[1]
                    > self._matching_stub_boundary_v015(a, b) + self.EDGE_TOL
                ]
                if len(intervals) >= 2:
                    refined_rows.append(intervals)
            return bool(refined_rows)

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
                row_refinement = False
                if mapping is not None:
                    counts = mapping["successor_columns_per_parent"]
                    same_grid_union = (
                        a["column_count"] == b["column_count"] and bool(counts)
                    )
                    expanded_union = (
                        b["column_count"] > a["column_count"]
                        and mapping["expanded"]
                        and len(counts) >= 2
                    )
                    row_refinement = self._continued_row_refinement_v016(
                        a, b, mapping
                    )
                    if not (same_grid_union or expanded_union or row_refinement):
                        mapping = None
                        row_refinement = False
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
                if row_refinement:
                    link_type = "STRUCTURAL_ROW_SPAN_REFINEMENT_CONTINUATION"
                    self._v016_rule_audit["row_span_refinement_links"] += 1
                elif mapping and mapping["expanded"]:
                    link_type = "STRUCTURAL_EXPANDED_HEADER_CONTINUATION"
                else:
                    link_type = "STRUCTURAL_GRID_CONTINUATION"
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
            incoming_confirmed = {
                link["to"] for link in links if link["status"] == "CONFIRMED"
            }

            for link in links:
                if (
                    link["status"] != "CONFIRMED"
                    or link.get("link_type")
                    != "STRUCTURAL_ROW_SPAN_REFINEMENT_CONTINUATION"
                ):
                    continue
                predecessor = by_id[link["from"]]
                successor = by_id[link["to"]]
                predecessor_probability, predecessor_ranking = (
                    self._candidate_probability_v016(predecessor, model, 0, 1)
                )
                successor_probability, successor_ranking = (
                    self._candidate_probability_v016(successor, model, 0, 1)
                )
                meta = {
                    "logical_table_id": predecessor["logical_table_id"],
                    "status": "STRUCTURAL_ROW_SPAN_REFINEMENT",
                    "header_rows_by_segment": [0, 0],
                    "stub_columns_by_segment": [1, 1],
                    "segment_count": 2,
                    "mapping_source": "NORMALIZED_GEOMETRIC_ROW_SPAN_UNION",
                }
                self._assign_prediction(
                    predecessor,
                    0,
                    1,
                    predecessor_probability,
                    predecessor_ranking,
                    {**meta, "physical_role": "OPEN_BODY_ROW"},
                )
                self._assign_prediction(
                    successor,
                    0,
                    1,
                    successor_probability,
                    successor_ranking,
                    {**meta, "physical_role": "CONTINUED_BODY_AND_LOCAL_BODY"},
                )
                predecessor["boundary_repair"] = "ROW_SPAN_REFINEMENT_BODY"
                successor["boundary_repair"] = "ROW_SPAN_REFINEMENT_BODY"
                self._v016_rule_audit["row_span_role_repairs"] += 1

            for table in tables:
                if (
                    table["table_id"] in incoming_confirmed
                    or table.get("boundary_repair") == "ROW_SPAN_REFINEMENT_BODY"
                    or table.get("boundary_confidence", 1.0) >= 0.75
                    or int(table.get("header_depth", 0)) < 2
                ):
                    continue
                proposal = self._narrative_boundary_proposal_v016(
                    table,
                    int(table["header_depth"]),
                    int(table["stub_column_count"]),
                )
                if not proposal:
                    continue
                probability, ranking = self._candidate_probability_v016(
                    table,
                    model,
                    proposal["header_rows"],
                    proposal["stub_columns"],
                )
                logical_meta = dict(table.get("logical_region_prediction") or {})
                logical_meta.update(
                    {
                        "local_header_rows": proposal["header_rows"],
                        "v016_boundary_repair": "NARRATIVE_LABEL_VALUE_BODY_START",
                    }
                )
                self._assign_prediction(
                    table,
                    proposal["header_rows"],
                    proposal["stub_columns"],
                    probability,
                    ranking,
                    logical_meta,
                )
                table["boundary_evidence"] = list(
                    dict.fromkeys(
                        [
                            *table.get("boundary_evidence", []),
                            "V016_REPEATED_LABEL_VALUE_BODY_GRAMMAR",
                            "V016_TYPED_OR_LONG_VALUE_SUPPORT",
                            "V016_PARENT_CHILD_HEADER_EXPANSION_REJECTED",
                            "V016_LOW_CONFIDENCE_GATE",
                        ]
                    )
                )
                table["boundary_repair"] = "NARRATIVE_LABEL_VALUE_BODY_START"
                self._v016_rule_audit["narrative_body_boundary_repairs"] += 1

            confirmed = {
                (link["from"], link["to"]): link
                for link in links
                if link["status"] == "CONFIRMED"
            }
            groups = defaultdict(list)
            for table in tables:
                groups[table["logical_table_id"]].append(table)
            for segments in groups.values():
                segments.sort(key=lambda item: (item["page"], item["bbox"][1]))
                if len(segments) < 2:
                    continue
                source = next(
                    (
                        segment
                        for segment in segments
                        if int(segment.get("header_depth", 0)) > 0
                        and int(segment.get("header_depth", 0))
                        < int(segment.get("row_count", 0))
                    ),
                    None,
                )
                if source is None:
                    continue
                for index in range(1, len(segments)):
                    predecessor, successor = segments[index - 1], segments[index]
                    if (predecessor["table_id"], successor["table_id"]) not in confirmed:
                        continue
                    if predecessor["column_count"] != successor["column_count"]:
                        continue
                    if int(successor.get("header_depth", 0)) != successor["row_count"]:
                        continue
                    repeated_depth = self._repeated_header_depth_v016(source, successor)
                    if repeated_depth:
                        continue
                    stub = int(source.get("stub_column_count", 1))
                    probability, ranking = self._candidate_probability_v016(
                        successor, model, 0, stub
                    )
                    logical_meta = dict(successor.get("logical_region_prediction") or {})
                    logical_meta.update(
                        {
                            "local_header_rows": 0,
                            "v016_boundary_repair": "INHERITED_HEADER_BODY_ONLY_SEGMENT",
                        }
                    )
                    self._assign_prediction(
                        successor, 0, stub, probability, ranking, logical_meta
                    )
                    successor["boundary_evidence"] = list(
                        dict.fromkeys(
                            [
                                *successor.get("boundary_evidence", []),
                                "V016_CONFIRMED_SAME_GRID_CONTINUATION",
                                "V016_CANONICAL_HEADER_INHERITED",
                                "V016_NO_REPEATED_LOCAL_HEADER",
                            ]
                        )
                    )
                    successor["boundary_repair"] = (
                        "INHERITED_HEADER_BODY_ONLY_SEGMENT"
                    )
                    self._v016_rule_audit["body_only_continuation_repairs"] += 1
            return inference

        def _apply_continuation_semantics(self, tables, links):
            super()._apply_continuation_semantics(tables, links)
            confirmed = {
                (link["from"], link["to"])
                for link in links
                if link["status"] == "CONFIRMED"
            }
            groups = defaultdict(list)
            for table in tables:
                groups[table["logical_table_id"]].append(table)
            for segments in groups.values():
                segments.sort(key=lambda item: (item["page"], item["bbox"][1]))
                if len(segments) < 2:
                    continue
                source = next(
                    (
                        segment
                        for segment in segments
                        if int(segment.get("header_depth", 0)) > 0
                    ),
                    None,
                )
                if source is None:
                    for index in range(1, len(segments)):
                        predecessor, successor = segments[index - 1], segments[index]
                        link = next(
                            (
                                item
                                for item in links
                                if item["from"] == predecessor["table_id"]
                                and item["to"] == successor["table_id"]
                                and item["status"] == "CONFIRMED"
                            ),
                            None,
                        )
                        if link and link.get("link_type") == (
                            "STRUCTURAL_ROW_SPAN_REFINEMENT_CONTINUATION"
                        ):
                            successor.pop("inherited_header", None)
                            successor.pop("logical_header_source_table_id", None)
                            predecessor.pop("logical_header_target_table_id", None)
                    continue
                header_matrix = source["matrix"][: int(source["header_depth"])]
                if not header_matrix:
                    continue
                for index in range(1, len(segments)):
                    predecessor, successor = segments[index - 1], segments[index]
                    if (predecessor["table_id"], successor["table_id"]) not in confirmed:
                        continue
                    successor["inherited_header"] = {
                        "source_table_id": source["table_id"],
                        "source_page": source["page"],
                        "matrix": header_matrix,
                        "status": "CANONICAL_STRUCTURAL_CONTINUATION_CONTEXT",
                    }
                    successor["logical_header_source_table_id"] = source["table_id"]
                    source["logical_header_target_table_id"] = successor["table_id"]
                    self._v016_rule_audit["canonical_header_inheritance_repairs"] += 1

        def build(self, raw):
            self._v016_rule_audit.clear()
            self._v016_filtered_block_keys.clear()
            result = super().build(raw)
            result["schema_version"] = "0.16"
            result["processing_policy"].update(
                {
                    "title_candidate_policy": "EXCLUDE_BLOCKS_INSIDE_ANY_PHYSICAL_TABLE",
                    "narrative_body_boundary_policy": "REPEATED_LABEL_VALUE_GRAMMAR_WITH_LOW_CONFIDENCE_GATE",
                    "continuation_local_header_policy": "INHERIT_CANONICAL_HEADER_AND_KEEP_BODY_ONLY_SEGMENTS_HEADERLESS",
                    "single_parent_expansion_policy": "GEOMETRIC_ROW_SPAN_REFINEMENT_ONLY",
                }
            )
            result["v0.16_rule_audit"] = dict(self._v016_rule_audit)
            result["annotation"]["annotation_source"] = (
                "SEMANTIC_PROMPT_TRANSFER_V0.16_CONTEXT_AND_CONTINUATION_REPAIRS"
            )
            return result

    DocumentBuilderV016.__name__ = "DocumentBuilderV016"
    return DocumentBuilderV016
