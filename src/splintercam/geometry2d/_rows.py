# SPDX-License-Identifier: Apache-2.0
"""Curve rows: the lines and arcs of closed loops at the kernel boundary (research 01, Kernel
arrays)."""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._curves import arc_inconsistency

_ROW_WIDTH = 7  # x0, y0, x1, y1, cx, cy, sweep


@dataclass(frozen=True, slots=True)
class CurveRows:
    """Closed loops of lines and arcs as arrays: `rows` (m, 7) float64 [x0, y0, x1, y1, cx, cy,
    sweep] in mm and radians, a line where sweep is 0 with a NaN centre; `ids` (m,) int64, one
    source ID per row; `row_starts` (k,) int64, the first row of each loop. Read-only; build them
    with `curve_rows`.
    """

    rows: NDArray[np.float64]
    ids: NDArray[np.int64]
    row_starts: NDArray[np.int64]


def _structure_error(
    rows: NDArray[np.generic], ids: NDArray[np.generic], starts: NDArray[np.generic]
) -> str | None:
    if rows.dtype != np.float64 or rows.ndim != 2 or rows.shape[1] != _ROW_WIDTH:
        return f"rows must be (m, {_ROW_WIDTH}) float64, got {rows.shape} {rows.dtype}"
    if ids.dtype != np.int64 or ids.shape != (rows.shape[0],):
        return f"ids must be ({rows.shape[0]},) int64, got {ids.shape} {ids.dtype}"
    if starts.dtype != np.int64 or starts.ndim != 1 or starts.size == 0:
        return f"row_starts must be (k,) int64 with k >= 1, got {starts.shape} {starts.dtype}"
    first = starts.view(np.int64)  # int64, checked above
    ends = np.append(first[1:], rows.shape[0])
    if first[0] != 0 or np.any(ends <= first):
        return f"row_starts must start at 0 and ascend strictly below {rows.shape[0]}: {starts}"
    return None


def _value_error(rows: NDArray[np.float64]) -> str | None:
    sweep = rows[:, 6]
    line = sweep == 0.0  # -0.0 too (REQ-G2D-189)
    centre = rows[:, 4:6]
    checks = (
        (line & ~np.isnan(centre).all(axis=1), "a line row has a centre"),
        (~line & ~np.isfinite(centre).all(axis=1), "an arc row has a non-finite centre"),
        (~np.isfinite(rows[:, [0, 1, 2, 3, 6]]).all(axis=1), "a row has a non-finite value"),
        (np.abs(sweep) > math.tau, "an arc row's sweep exceeds 2π"),
    )
    for broken, what in checks:
        if broken.any():
            return f"{what} (row {int(np.flatnonzero(broken)[0])})"
    return None


def _continuity_error(
    rows: NDArray[np.float64], starts: NDArray[np.int64], closed: bool
) -> str | None:
    # Each row starts bit for bit where the row before it in its loop ends; the first row of a
    # loop follows the loop's last row (research 01, Kernel arrays), not that of an open chain.
    bits = rows.view(np.int64)
    previous = np.arange(rows.shape[0], dtype=np.int64) - 1
    ends = np.append(starts[1:], rows.shape[0])
    previous[starts] = ends - 1
    gaps = (bits[:, 0:2] != bits[previous, 2:4]).any(axis=1)
    gaps[starts] &= closed
    if gaps.any():
        return f"row {int(np.flatnonzero(gaps)[0])} does not start where the row before it ends"
    return None


def curve_rows(
    rows: ArrayLike, ids: ArrayLike, row_starts: ArrayLike, ctx: Context
) -> Result[CurveRows]:
    """Validated, read-only, C-contiguous copies of curve rows.

    `CURVE_INVALID` for a broken structure, value or continuity; `ARC_INCONSISTENT` for an arc row
    whose P1 is off its circle or whose sweep does not fit its end points (Peter, 2026-10-02).

    Implements: REQ-G2D-188 to 194, REQ-G2D-196, REQ-G2D-197, REQ-G2D-201.
    """
    return checked_rows(rows, ids, row_starts, ctx, closed=True)


def checked_rows(
    rows: ArrayLike, ids: ArrayLike, row_starts: ArrayLike, ctx: Context, closed: bool
) -> Result[CurveRows]:
    """`curve_rows`, with the closure of each loop checked only when `closed` (internal)."""
    copies = [np.array(value, order="C", copy=True) for value in (rows, ids, row_starts)]
    rows_copy, ids_copy, starts_copy = copies
    error = _structure_error(rows_copy, ids_copy, starts_copy)
    error = error or _value_error(rows_copy) or _continuity_error(rows_copy, starts_copy, closed)
    if error is not None:
        return Result(None, (Diagnostic("CURVE_INVALID", Severity.ERROR, error),))
    inconsistency = arc_inconsistency(rows_copy, ctx.tolerances.length_eps_mm)
    if inconsistency is not None:
        return Result(None, (Diagnostic("ARC_INCONSISTENT", Severity.ERROR, inconsistency),))
    for copy in copies:
        copy.flags.writeable = False
    return Result(CurveRows(rows_copy, ids_copy, starts_copy))
