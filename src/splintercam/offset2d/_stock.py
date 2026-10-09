# SPDX-License-Identifier: Apache-2.0
"""The stock update without chaining (research 02, Booleans, RR-001): each operation's machined
area from its own centre paths, a stock layer as the raw layer minus all machined areas in one
call (D-026, DEC-OFF-006, DEC-OFF-007)."""

import math
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

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
from ._chain import grow_flat_chains
from ._classes import SourceClasses, check_classes
from ._results import (
    MARGIN_GRID_UNITS,
    outcome,
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
    status, region = grow_flat_chains(flat, delta, delta + margin_mm, classes, ctx)

    def dump() -> dict[str, object]:
        return {"chains": [p.tolist() for p, _ in flat], "delta_mm": delta,
                "arc_tol_mm": tol.arc_tol_mm, "grid_unit_mm": tol.grid_unit_mm}  # fmt: skip

    return outcome(status, region, dump, diagnostics, ctx)


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
