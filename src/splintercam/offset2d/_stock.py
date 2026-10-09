# SPDX-License-Identifier: Apache-2.0
"""The stock update without chaining (research 02, Booleans, RR-001): each operation's machined
area from its own centre paths, a stock layer as the raw layer minus all machined areas in one
call (D-026, DEC-OFF-006, DEC-OFF-007)."""

import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import CANCELLED, Context, Diagnostic, Result
from splintercam.geometry2d import (
    AirSide,
    CurveRows,
    PolygonRegion,
    RegionKind,
    build_chain,
    flatten_loops,
    loop_tree,
)

from ._boolean import BooleanOp, clip
from ._classes import SourceClasses, check_classes
from ._results import (
    JOIN_STEPS_MAX,
    MARGIN_GRID_UNITS,
    MAX_SPAN_GRID_UNITS,
    outcome,
    run_kernel,
    vertex_classes,
)

Chain = tuple[NDArray[np.float64], NDArray[np.int64]]  # the rows and IDs of one centre path


def machined_area(
    paths: Sequence[Chain], tool_radius_mm: float, classes: SourceClasses, ctx: Context
) -> Result[PolygonRegion]:
    """The area an operation's tool of radius R swept along its centre paths, never larger than
    the true one: each path flattened within t_flat (geometry2d's `build_chain`, open or closed),
    all grown together by R - m, m = t_flat + 6u, with round joins and ends and no bias.

    Implements: REQ-OFF-031, REQ-OFF-032.
    """
    tol = ctx.tolerances
    margin_mm = MARGIN_GRID_UNITS * tol.grid_unit_mm
    m_mm = tol.flatten_tol_mm + margin_mm  # what the flattening and two roundings may cost (RR-001)
    # δ = R - m must exceed the arc tolerance a, or a round join has no step (DEC-OFF-015).
    least = m_mm + tol.arc_tol_mm
    if not (math.isfinite(tool_radius_mm) and tool_radius_mm > least):
        raise ValueError(f"the tool radius must be finite and > {least} mm, got {tool_radius_mm!r}")
    check_classes(classes, np.concatenate([ids for _, ids in paths] or [np.empty(0, np.int64)]))
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    flat: list[tuple[NDArray[np.float64], NDArray[np.int64]]] = []
    diagnostics: list[Diagnostic] = []
    for rows, ids in paths:  # a loop over centre paths, not over points
        chain = build_chain(rows, ids, AirSide.LEFT, ctx)  # either side: m pays for it
        diagnostics += chain.diagnostics
        if chain.value is None:
            return Result(None, tuple(diagnostics))
        flat.append((chain.value.points, chain.value.source_ids))
    delta = tool_radius_mm - m_mm
    status, region = _grow(flat, delta, classes, ctx)

    def dump() -> dict[str, object]:
        return {"chains": [p.tolist() for p, _ in flat], "delta_mm": delta,
                "arc_tol_mm": tol.arc_tol_mm, "grid_unit_mm": tol.grid_unit_mm}  # fmt: skip

    return outcome(status, region, dump, diagnostics, ctx)


def _grow(
    flat: list[tuple[NDArray[np.float64], NDArray[np.int64]]],
    delta: float,
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
    # The grown boundary lies within [δ - a - 3u, δ + 3u] of the flattened chains (research 02,
    # The kernel call, steps 5 and 6), so δ plus the rounding margin reaches its source edge.
    offset = (delta, tol.arc_tol_mm, delta + MARGIN_GRID_UNITS * tol.grid_unit_mm)
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


def stock_layer(
    raw: CurveRows, machined: Sequence[PolygonRegion], classes: SourceClasses, ctx: Context
) -> Result[PolygonRegion]:
    """A stock layer: the raw layer, flattened as material (toward more stock), minus the machined
    areas of all operations so far in one Difference call, never from an earlier stock layer.

    Implements: REQ-OFF-031, REQ-OFF-044.
    """
    check_classes(classes, raw.ids)
    tree = loop_tree(raw, ctx)
    diagnostics = list(tree.diagnostics)
    if tree.value is None or not tree.ok:
        return Result(None, tuple(diagnostics))
    layer = flatten_loops(tree.value, RegionKind.MATERIAL, ctx).region
    regions = list(machined)
    offsets = np.cumsum([0, *[r.points.shape[0] for r in regions]], dtype=np.int64)[:-1]
    cut = PolygonRegion(  # the loops of all machined areas, united by the Positive rule in the call
        np.concatenate([r.points for r in regions] or [np.empty((0, 2))]),
        np.concatenate([r.loop_starts + o for r, o in zip(regions, offsets, strict=True)]
                       or [np.empty(0, np.int64)]).astype(np.int64),
        np.concatenate([r.source_ids for r in regions] or [np.empty(0, np.int64)]).astype(np.int64),
        np.concatenate([r.fixed for r in regions] or [np.empty(0, np.uint8)]).astype(np.uint8),
    )  # fmt: skip
    check_classes(classes, cut.source_ids)
    if ctx.cancel.is_cancelled:
        return Result(None, (*diagnostics, CANCELLED))
    status, region = clip(layer, cut, BooleanOp.DIFFERENCE, classes, ctx)

    def dump() -> dict[str, object]:
        return {"layer": layer.points.tolist(), "machined": cut.points.tolist(),
                "grid_unit_mm": ctx.tolerances.grid_unit_mm}  # fmt: skip

    return outcome(status, region, dump, diagnostics, ctx)
