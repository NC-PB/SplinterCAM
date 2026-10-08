# SPDX-License-Identifier: Apache-2.0
"""The bridge to Clipper2's integer grid (research 01, Tolerances, resolution chain; D-058,
D-132)."""

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._polygon import PolygonRegion

# A Clipper2 call refuses input spanning 2^26 grid units or more (SRC-122; research 01,
# Parameters): a named constant for now, provisionally (DEC-G2D-034).
MAX_SPAN_GRID_UNITS = float(2**26)
_OK, _TOO_LARGE, _FAILED = 0, 1, 2  # GridStatus in kernel/grid.hpp


def _region(points: NDArray[np.float64], starts: NDArray[np.int64]) -> PolygonRegion:
    n = points.shape[0]
    arrays = (points, starts, np.full(n, -1, dtype=np.int64), np.zeros(n, dtype=np.uint8))
    for array in arrays:
        array.flags.writeable = False
    return PolygonRegion(*arrays)


def grid_union(
    points: NDArray[np.float64], loop_starts: NDArray[np.int64], ctx: Context
) -> Result[PolygonRegion]:
    """The union with the NonZero fill rule of closed polylines (a polygon region's layout),
    through Clipper2's grid: re-centred on the input's bounding box and rounded to u
    (REQ-G2D-033), refused with `REGION_TOO_LARGE` when the input spans 2^26 grid units or more
    (REQ-G2D-034). Source IDs are -1. Internal, for research 01 test 21 (D-060).

    Implements: REQ-G2D-029, REQ-G2D-030, REQ-G2D-033, REQ-G2D-034.
    """
    u = ctx.tolerances.grid_unit_mm
    vertices = np.ascontiguousarray(points, dtype=np.float64)
    starts = np.ascontiguousarray(loop_starts, dtype=np.int64)
    room = vertices.shape[0] + 8
    while True:
        out, out_starts = np.empty((room, 2)), np.empty(room, dtype=np.int64)
        kernel = _kernels.geometry2d
        status, n_points, n_loops = kernel.grid_union(
            vertices, starts, u, MAX_SPAN_GRID_UNITS, out, out_starts
        )
        if max(n_points, n_loops) <= room:
            break
        room = max(n_points, n_loops)
    if status == _TOO_LARGE:
        message = f"the input spans {MAX_SPAN_GRID_UNITS:.0f} grid units of {u} mm or more"
        return Result(None, (Diagnostic("REGION_TOO_LARGE", Severity.ERROR, message),))
    if status == _FAILED:
        return Result(None, (Diagnostic("REGION_FAILED", Severity.ERROR, "Clipper2 failed"),))
    return Result(_region(out[:n_points].copy(), out_starts[:n_loops].copy()))
