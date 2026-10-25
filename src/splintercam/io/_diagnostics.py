# SPDX-License-Identifier: Apache-2.0
"""The io diagnostic codes and the deterministic order they are returned in (REQ-IO-028,
REQ-IO-029). Every io diagnostic is collected with a sort key and emitted once, sorted, so the
same file and arguments give the same diagnostics in the same order (D-055)."""

from splintercam.foundation import Diagnostic, Severity

# File-level (REQ-IO-002, 005 to 008, 025); the first group, each returned with no value.
DXF_UNREADABLE = "DXF_UNREADABLE"
DXF_NO_UNITS = "DXF_NO_UNITS"
DXF_UNIT_UNSUPPORTED = "DXF_UNIT_UNSUPPORTED"
DXF_UNIT_CONFLICT = "DXF_UNIT_CONFLICT"
DXF_LAYER_EMPTY = "DXF_LAYER_EMPTY"
# Skipped entity types (REQ-IO-003).
DXF_SKIPPED = "DXF_SKIPPED"
# Entity-level (REQ-IO-010, 011, 015, 016, 017).
DXF_NOT_PLANAR = "DXF_NOT_PLANAR"
DXF_ENTITY_INVALID = "DXF_ENTITY_INVALID"
DXF_ENTITY_TOO_LARGE = "DXF_ENTITY_TOO_LARGE"
DXF_DEGENERATE = "DXF_DEGENERATE"
DXF_DUPLICATE = "DXF_DUPLICATE"
# Junction-level (REQ-IO-019, 022).
DXF_BRANCH = "DXF_BRANCH"
DXF_GAP_CLOSED = "DXF_GAP_CLOSED"
DXF_GAP_NOT_CLOSED = "DXF_GAP_NOT_CLOSED"
# Chain and contour (REQ-IO-026).
DXF_OPEN_CHAIN = "DXF_OPEN_CHAIN"
DXF_CONTOUR_COUNT = "DXF_CONTOUR_COUNT"
# Success (REQ-IO-027).
DXF_PART_SIZE = "DXF_PART_SIZE"

# Groups of REQ-IO-029, in the order diagnostics are returned.
_GROUP_FILE = 0
_GROUP_SKIPPED = 1
_GROUP_ENTITY = 2
_GROUP_JUNCTION = 3
_GROUP_OPEN_CHAIN = 4
_GROUP_CONTOUR = 5
_GROUP_CURVE_ROWS = 6
_GROUP_PART_SIZE = 7

# Code order within the entity and junction groups (REQ-IO-029: "then code").
_ENTITY_CODE_RANK = {
    DXF_ENTITY_INVALID: 0,
    DXF_NOT_PLANAR: 1,
    DXF_ENTITY_TOO_LARGE: 2,
    DXF_DEGENERATE: 3,
    DXF_DUPLICATE: 4,
}
_JUNCTION_CODE_RANK = {DXF_BRANCH: 0, DXF_GAP_CLOSED: 1, DXF_GAP_NOT_CLOSED: 2}


class Collector:
    """Gathers diagnostics with their sort keys and emits them once in REQ-IO-029 order."""

    def __init__(self) -> None:
        self._items: list[tuple[tuple[object, ...], Diagnostic]] = []

    def _add(self, key: tuple[object, ...], diagnostic: Diagnostic) -> None:
        self._items.append((key, diagnostic))

    def file(self, code: str, message: str, severity: Severity = Severity.ERROR) -> None:
        self._add((_GROUP_FILE,), Diagnostic(code, severity, message))

    def skipped(self, type_name: str, count: int) -> None:
        message = f"skipped {count} {type_name} {'entity' if count == 1 else 'entities'}"
        self._add((_GROUP_SKIPPED, type_name), Diagnostic(DXF_SKIPPED, Severity.INFO, message))

    def entity(
        self, code: str, severity: Severity, entity_index: int, segment: int, message: str
    ) -> None:
        key = (_GROUP_ENTITY, entity_index, segment, _ENTITY_CODE_RANK[code])
        self._add(key, Diagnostic(code, severity, message, location=f"entity {entity_index}"))

    def junction(self, code: str, severity: Severity, x: float, y: float, message: str) -> None:
        key = (_GROUP_JUNCTION, x, y, _JUNCTION_CODE_RANK[code])
        self._add(key, Diagnostic(code, severity, message, location=f"({x:.6g}, {y:.6g}) mm"))

    def open_chain(self, min_source_id: int, message: str) -> None:
        key = (_GROUP_OPEN_CHAIN, min_source_id)
        self._add(key, Diagnostic(DXF_OPEN_CHAIN, Severity.ERROR, message))

    def contour_count(self, message: str) -> None:
        self._add((_GROUP_CONTOUR,), Diagnostic(DXF_CONTOUR_COUNT, Severity.ERROR, message))

    def curve_rows(self, diagnostics: tuple[Diagnostic, ...]) -> None:
        for order, diagnostic in enumerate(diagnostics):
            self._add((_GROUP_CURVE_ROWS, order), diagnostic)

    def part_size(self, message: str) -> None:
        self._add((_GROUP_PART_SIZE,), Diagnostic(DXF_PART_SIZE, Severity.INFO, message))

    def has_error(self) -> bool:
        return any(d.severity is Severity.ERROR for _, d in self._items)

    def emit(self) -> tuple[Diagnostic, ...]:
        return tuple(diagnostic for _, diagnostic in sorted(self._items, key=lambda item: item[0]))
