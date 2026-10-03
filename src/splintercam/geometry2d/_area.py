# SPDX-License-Identifier: Apache-2.0
"""The signed area of a loop of lines and arcs (research 01, Area and orientation)."""

import numpy as np

from splintercam import _kernels
from splintercam.foundation import TOLERANCE_DEFAULTS, Context, Diagnostic, Result, Severity

from ._rows import CurveRows

# Declared parameters (REQ-G2D-230): beyond either, the polygon part is summed exactly.
_FLOAT_MAX_VERTICES = TOLERANCE_DEFAULTS["area_float_max_vertices"].default
_FLOAT_MAX_HALF_EXTENT_MM = TOLERANCE_DEFAULTS["area_float_max_half_extent_mm"].default


def signed_area(loop: CurveRows, ctx: Context) -> Result[float]:
    """The signed area of one loop in mm², positive counter-clockwise, or no value and
    `LOOP_DEGENERATE` when |A| <= eps_len·L. More than one loop is a `ValueError`.

    Implements: REQ-G2D-001, REQ-G2D-002, REQ-G2D-128, REQ-G2D-130 to 133.
    """
    if loop.row_starts.size != 1:
        raise ValueError(f"signed_area takes one loop, got {loop.row_starts.size}")
    rows = np.ascontiguousarray(loop.rows, dtype=np.float64)
    # The bounding box of the end points; every end point starts a row of the closed loop.
    low, high = rows[:, :2].min(axis=0), rows[:, :2].max(axis=0)
    centre = (low + high) / 2
    half_extent = float((high - low).max()) / 2
    exact = rows.shape[0] > _FLOAT_MAX_VERTICES or half_extent > _FLOAT_MAX_HALF_EXTENT_MM
    out = np.zeros(2)
    _kernels.geometry2d.loop_area(rows, float(centre[0]), float(centre[1]), exact, out)
    area, length = float(out[0]), float(out[1])
    if abs(area) <= ctx.tolerances.length_eps_mm * length:
        message = f"|A| = {abs(area):.3g} mm² is at most eps_len·L for L = {length:.6g} mm"
        return Result(None, (Diagnostic("LOOP_DEGENERATE", Severity.WARNING, message),))
    return Result(area)
