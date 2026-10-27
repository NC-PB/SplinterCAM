# SPDX-License-Identifier: Apache-2.0
"""What the writer refuses, in the order of REQ-NCX-017: the program, then each operation's
errors by requirement ID and, within one, by move index (D-055)."""

import math
import re

import numpy as np
from numpy.typing import NDArray

from splintercam.cl import ClHeader, ClOperation, MoveKind
from splintercam.foundation import Diagnostic, Severity

from ._moves import CENTRE_X, CENTRE_Y, Printed, X, Y
from ._printer import VALUE_LIMIT

# Research 27, Checked condition 2: names valid as file names on every platform; Microsoft,
# "Naming Files, Paths, and Namespaces": the device names Windows reserves.
_NAME = re.compile(r"[A-Za-z0-9_]+")
_DEVICES = frozenset(
    ("CON", "PRN", "AUX", "NUL", *(f"{port}{n}" for port in ("COM", "LPT") for n in range(1, 10)))
)
# DEC-NCX-009: outside printable ASCII, a bracket (ends a Fanuc comment) or NCX's escape `\`.
_NOT_IN_NOTE = re.compile(r"[^\x20-\x7e]|[()\\]")


def _error(code: str, message: str, location: str) -> Diagnostic:
    return Diagnostic(code, Severity.ERROR, message, location)


def program_errors(name: str, number: int) -> list[Diagnostic]:
    """REQ-NCX-014: the program's name, then its number."""
    found: list[Diagnostic] = []
    if _NAME.fullmatch(name) is None or name.upper() in _DEVICES:
        message = (
            f"program name {name!r}: use ASCII letters, digits and underscores, no device name"
        )
        found.append(_error("NCX_PROGRAM_NAME_INVALID", message, "program"))
    if number < 1:
        message = f"program number {number} is below 1"
        found.append(_error("NCX_PROGRAM_NUMBER_INVALID", message, "program"))
    return found


def _degenerate_arcs(operation: ClOperation, columns: Printed) -> NDArray[np.intp]:
    # REQ-NCX-016 on the printed counts; the start is the previous move's end, unknown in the
    # plane for move 1 (REQ-CL-006); moves with a value too large are reported already.
    moves, counts = operation.moves, columns.counts
    arcs = np.flatnonzero(moves.kind == MoveKind.ARC)
    arcs = arcs[(arcs > 1) & ~columns.too_large[arcs] & ~columns.too_large[arcs - 1]]
    start, end = counts[arcs - 1][:, [X, Y]], counts[arcs][:, [X, Y]]
    centre = counts[arcs][:, [CENTRE_X, CENTRE_Y]]

    def same(a: NDArray[np.int64], b: NDArray[np.int64]) -> NDArray[np.bool_]:
        return np.all(a == b, axis=1)

    partial = np.abs(moves.sweep_rad[arcs]) < math.tau
    return arcs[(partial & same(end, start)) | same(centre, start) | same(centre, end)]


def operation_errors(
    where: str, operation: ClOperation, first: ClHeader, columns: Printed
) -> list[Diagnostic]:
    """REQ-NCX-003, 010, 013, 015 and 016 for one operation, in that order."""
    header = operation.header
    found: list[Diagnostic] = []
    if (header.tool_number, header.spindle_rpm) != (first.tool_number, first.spindle_rpm):
        message = (
            f"tool {header.tool_number} at {header.spindle_rpm} 1/min differs from the first "
            f"operation's tool {first.tool_number} at {first.spindle_rpm} 1/min; one tool and "
            "one speed per program (DEC-NCX-004)"
        )
        found.append(_error("NCX_TOOL_CHANGE_UNSUPPORTED", message, where))
    if header.spindle_rpm >= VALUE_LIMIT:
        message = f"spindle speed {header.spindle_rpm} 1/min is 10^9 or more"
        found.append(_error("NCX_VALUE_OUT_OF_RANGE", message, where))
    for move in np.flatnonzero(columns.too_large):
        message = f"move {move}: a coordinate or feed of 10^9 or more"
        found.append(_error("NCX_VALUE_OUT_OF_RANGE", message, where))
    if header.point_number != 1:
        message = f"point {header.point_number}: only point 1 until NCX has point words (AQ-005)"
        found.append(_error("NCX_POINT_UNSUPPORTED", message, where))
    for index, line in enumerate(header.note, start=1):
        character = _NOT_IN_NOTE.search(line)
        if character is not None:
            message = f"note line {index} holds {character.group()!r} (DEC-NCX-009)"
            found.append(_error("NCX_NOTE_CHARACTER", message, where))
    for move in _degenerate_arcs(operation, columns):
        message = f"move {move}: the arc prints with its end at its start or its centre at an end"
        found.append(_error("NCX_ARC_PRINTS_DEGENERATE", message, where))
    return found
