# SPDX-License-Identifier: Apache-2.0
"""Open chains grown on both sides (research 02, Open chains): for link checks (D-062) and, through
`grow_flat_chains`, for the machined area of the stock update."""

import math

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity
from splintercam.geometry2d import AirSide, PolygonRegion, build_chain

from ._classes import SourceClasses, check_classes
from ._results import (
    BIAS_GRID_UNITS,
    JOIN_STEPS_MAX,
    MARGIN_GRID_UNITS,
    MAX_SPAN_GRID_UNITS,
    outcome,
    run_kernel,
    vertex_classes,
)


def grow_chain(
    rows: NDArray[np.float64],
    ids: NDArray[np.int64],
    clearance_mm: float,
    classes: SourceClasses,
    ctx: Context,
) -> Result[PolygonRegion]:
    """The area within t of one open chain, with round ends: the chain flattened by geometry2d's
    `build_chain` and grown by δ = t + t_flat + a + 3u, so it covers t from the true chain on both
    sides of every arc. A closed chain is refused with `CHAIN_CLOSED`.

    Implements: REQ-OFF-013, REQ-OFF-027, REQ-OFF-029, REQ-OFF-031.
    """
    if not (math.isfinite(clearance_mm) and clearance_mm > 0.0):
        raise ValueError(f"the clearance must be finite and > 0, got {clearance_mm!r}")
    check_classes(classes, np.asarray(ids, dtype=np.int64))
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    chain = build_chain(rows, ids, AirSide.LEFT, ctx)  # either side: δ adds t_flat
    if chain.value is None:
        return Result(None, chain.diagnostics)
    points = chain.value.points
    if points.shape[0] > 1 and bool(np.all(points[0] == points[-1])):  # bit for bit (DEC-OFF-017)
        message = "the chain closes: a loop goes through offset_region"
        return Result(
            None, (*chain.diagnostics, Diagnostic("CHAIN_CLOSED", Severity.ERROR, message))
        )
    tol = ctx.tolerances
    delta = clearance_mm + tol.flatten_tol_mm + tol.arc_tol_mm + BIAS_GRID_UNITS * tol.grid_unit_mm
    # The boundary lies within [t, t + t_flat + a + 6u] of the flattened chain, δ + 3u at most, so
    # δ plus the rounding margin reaches the source edge of every output edge's middle.
    reach = delta + MARGIN_GRID_UNITS * tol.grid_unit_mm
    flat = [(points, chain.value.source_ids)]
    status, region = grow_flat_chains(flat, delta, reach, classes, ctx)

    def dump() -> dict[str, object]:
        return {"chain": points.tolist(), "delta_mm": delta, "arc_tol_mm": tol.arc_tol_mm,
                "grid_unit_mm": tol.grid_unit_mm}  # fmt: skip

    return outcome(status, region, dump, list(chain.diagnostics), ctx)


def grow_flat_chains(
    flat: list[tuple[NDArray[np.float64], NDArray[np.int64]]],
    delta: float,
    reach: float,
    classes: SourceClasses,
    ctx: Context,
) -> tuple[int, PolygonRegion | None]:
    """The kernel call: the chains, and for the IDs each chain there and back, so every segment
    is an edge of a closed polyline twice with its own ID and no closing edge is invented."""
    tol = ctx.tolerances
    points = np.concatenate([p for p, _ in flat] or [np.empty((0, 2))])
    starts = np.cumsum([0, *[p.shape[0] for p, _ in flat]], dtype=np.int64)[:-1]
    there_back = [np.concatenate([p, p[-2:0:-1]]) for p, _ in flat]
    back_ids = [np.concatenate([s, s[-1:], s[-2::-1]]) for _, s in flat]
    id_points = np.concatenate(there_back or [np.empty((0, 2))])
    id_starts = np.cumsum([0, *[q.shape[0] for q in there_back]], dtype=np.int64)[:-1]
    ids = np.concatenate(back_ids or [np.empty(0, np.int64)]).astype(np.int64)
    per_vertex = vertex_classes(classes, ids)
    offset = (delta, tol.arc_tol_mm, reach)
    grid = (tol.grid_unit_mm, MAX_SPAN_GRID_UNITS, JOIN_STEPS_MAX, tol.length_eps_mm)
    steps = math.pi / math.acos(1.0 - tol.arc_tol_mm / delta)

    def call(
        out_points: NDArray[np.float64],
        out_starts: NDArray[np.int64],
        out_ids: NDArray[np.int64],
        out_fixed: NDArray[np.uint8],
    ) -> tuple[int, int, int]:
        return _kernels.offset2d.grow_chains(
            points, starts, id_points, id_starts, ids, per_vertex, offset, grid,
            out_points, out_starts, out_ids, out_fixed,
        )  # fmt: skip

    return run_kernel(call, 2 * points.shape[0] + math.ceil(steps) * (len(flat) + 1) + 64)
