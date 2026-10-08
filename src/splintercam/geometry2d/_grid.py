# SPDX-License-Identifier: Apache-2.0
"""The bridge to Clipper2's integer grid (research 01, Tolerances, resolution chain; D-058,
D-132)."""

import enum

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._polygon import PolygonRegion

# A Clipper2 call refuses input spanning 2^26 grid units or more (SRC-122; research 01,
# Parameters): a named constant for now, provisionally (DEC-G2D-034).
MAX_SPAN_GRID_UNITS = float(2**26)
_OK, _TOO_LARGE = 0, 1  # GridStatus in kernel/grid.hpp; 2 is a Clipper2 failure
# Output edges lie within 2.83 grid units of the flattened input (REQ-G2D-030); twice t_topo
# (4 grid units) reaches the nearest input edge from every output edge's middle.
_ID_REACH_T_TOPO = 2.0


class FillRule(enum.IntEnum):
    """Clipper2's fill rules, numbered as Clipper2Lib::FillRule (internal, for REQ-G2D-177)."""

    EVEN_ODD = 0
    NON_ZERO = 1
    POSITIVE = 2


def region_with_fill_rule(
    region: PolygonRegion, fill_rule: FillRule, ctx: Context
) -> Result[PolygonRegion]:
    """Flattened loops joined on the grid with the given fill rule: re-centred on their bounding
    box and rounded to u, refused with `REGION_TOO_LARGE` when they span 2^26 grid units or more,
    pinch points split and fixed, source IDs from the nearest input edge (internal;
    `build_region` uses Positive).

    Implements: REQ-G2D-030, REQ-G2D-032 to 034, REQ-G2D-176, REQ-G2D-177, REQ-G2D-180,
    REQ-G2D-181.
    """
    tol = ctx.tolerances
    grid = (tol.grid_unit_mm, MAX_SPAN_GRID_UNITS, _ID_REACH_T_TOPO * tol.topology_tol_mm)
    room = region.points.shape[0] + 8
    while True:
        points, starts = np.empty((room, 2)), np.empty(room, dtype=np.int64)
        ids, fixed = np.empty(room, dtype=np.int64), np.empty(room, dtype=np.uint8)
        status, n_points, n_loops = _kernels.geometry2d.grid_region(
            region.points, region.loop_starts, region.source_ids, int(fill_rule), grid,
            points, starts, ids, fixed,
        )  # fmt: skip
        if max(n_points, n_loops) <= room:
            break
        room = max(n_points, n_loops)
    if status == _TOO_LARGE:
        message = (
            f"the input spans {MAX_SPAN_GRID_UNITS:.0f} grid units of {tol.grid_unit_mm} mm or more"
        )
        return Result(None, (Diagnostic("REGION_TOO_LARGE", Severity.ERROR, message),))
    if status != _OK:
        return Result(None, (Diagnostic("REGION_FAILED", Severity.ERROR, "Clipper2 failed"),))
    out = PolygonRegion(
        points[:n_points].copy(),
        starts[:n_loops].copy(),
        ids[:n_points].copy(),
        fixed[:n_points].copy(),
    )
    for array in (out.points, out.loop_starts, out.source_ids, out.fixed):
        array.flags.writeable = False
    return Result(out)


def grid_union(
    points: NDArray[np.float64], loop_starts: NDArray[np.int64], ctx: Context
) -> Result[PolygonRegion]:
    """The union with the NonZero fill rule of closed polylines (a polygon region's layout)
    through the grid, as `region_with_fill_rule`; source IDs -1. Internal, for research 01 test 21
    (D-060).

    Implements: REQ-G2D-029, REQ-G2D-030, REQ-G2D-033, REQ-G2D-034.
    """
    vertices = np.ascontiguousarray(points, dtype=np.float64)
    n = vertices.shape[0]
    starts = np.ascontiguousarray(loop_starts, dtype=np.int64)
    region = PolygonRegion(vertices, starts, np.full(n, -1, np.int64), np.zeros(n, np.uint8))
    return region_with_fill_rule(region, FillRule.NON_ZERO, ctx)
