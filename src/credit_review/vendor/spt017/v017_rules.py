from __future__ import annotations

from collections import Counter


def install_v017_builder(base_class):
    """Return the v0.17 builder with merge-safe header-boundary repair.

    v0.16 deliberately shortens only low-confidence over-deep headers.  A body
    boundary must nevertheless never cut a measure-side vertical merge, and a
    row that expands a preceding horizontal parent merge into multiple textual
    children is still a header row.  These are structural guards; no lexical
    table meaning is used.
    """

    class DocumentBuilderV017(base_class):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._v017_rule_audit = Counter()

        def _crosses_measure_vertical_merge_v017(self, table, boundary, stub):
            for merge in self._restore_merge_spans(table) or []:
                row = int(merge.get("row", -1))
                row_span = int(merge.get("row_span", 1))
                column = int(merge.get("column", -1))
                col_span = int(merge.get("col_span", 1))
                if row_span <= 1:
                    continue
                if not (row < boundary < row + row_span):
                    continue
                if column + col_span <= stub:
                    continue
                return True
            return False

        def _expands_prior_parent_merge_v017(self, table, boundary):
            matrix = table.get("matrix") or []
            if boundary <= 0 or boundary >= len(matrix):
                return False
            row = matrix[boundary]
            for merge in self._restore_merge_spans(table) or []:
                parent_row = int(merge.get("row", -1))
                start = int(merge.get("column", -1))
                span = int(merge.get("col_span", 1))
                if parent_row >= boundary or span <= 1 or start < 0:
                    continue
                end = min(len(row), start + span)
                children = [
                    self._clean(row[column])
                    for column in range(start, end)
                    if self._clean(row[column])
                ]
                if len(children) < 2:
                    continue
                if all(
                    self._value_kind_v015(value)
                    not in {"NUMBER", "DATE", "MISSING"}
                    for value in children
                ):
                    return True
            return False

        def _narrative_boundary_proposal_v016(self, table, current_h, current_s):
            proposal = super()._narrative_boundary_proposal_v016(
                table, current_h, current_s
            )
            if not proposal:
                return None
            boundary = int(proposal["header_rows"])
            stub = int(proposal["stub_columns"])
            if self._crosses_measure_vertical_merge_v017(table, boundary, stub):
                self._v017_rule_audit[
                    "narrative_repairs_blocked_by_vertical_merge"
                ] += 1
                return None
            if self._expands_prior_parent_merge_v017(table, boundary):
                self._v017_rule_audit[
                    "narrative_repairs_blocked_by_parent_child_expansion"
                ] += 1
                return None
            return proposal

        def build(self, raw):
            master = super().build(raw)
            master["v0.17_rule_audit"] = dict(self._v017_rule_audit)
            return master

    DocumentBuilderV017.__name__ = "DocumentBuilderV017"
    return DocumentBuilderV017
