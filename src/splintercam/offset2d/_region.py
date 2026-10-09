# SPDX-License-Identifier: Apache-2.0
"""The region offset (research 02, Definitions and The kernel call): a region of air shrinks, a
region of material grows by a clearance t, in one Clipper2 call on geometry2d's grid."""

import math

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import (
    CANCELLED,
    TOLERANCE_DEFAULTS,
    Context,
    Diagnostic,
    Result,
)
from splintercam.geometry2d import (
    CurveRows,
    PolygonRegion,
    RegionKind,
    build_region,
    cleanup,
    flatten_loops,
    loop_tree,
)

from ._classes import SourceClasses, check_classes
from ._results import (
    BIAS_GRID_UNITS,
    JOIN_STEPS_MAX,
    MARGIN_GRID_UNITS,
    MAX_SPAN_GRID_UNITS,
    OK,
    outcome,
    run_kernel,
    vertex_classes,
)

_ARC_TOL_FLOOR_GRID_UNITS = TOLERANCE_DEFAULTS["arc_tol_floor_grid_units"].default  # D-132


def offset_region(
    loops: CurveRows,
    kind: RegionKind,
    clearance_mm: float,
    classes: SourceClasses,
    ctx: Context,
) -> Result[PolygonRegion]:
    """The region of `loops` offset by the clearance t: a region of air shrunk to the points at
    least t from every loop, a region of material grown by t (research 02, Definitions). t = 0
    gives `build_region`'s region. The loop tree's and the clean-up's diagnostics are passed on.

    Implements: REQ-OFF-013, REQ-OFF-014, REQ-OFF-018, REQ-OFF-020 to 022, REQ-OFF-024 to 026,
    REQ-OFF-034, REQ-OFF-039 to 043.
    """
    _check_arguments(loops, kind, clearance_mm, classes, ctx)
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    if clearance_mm == 0.0:
        built = build_region(loops, kind, ctx)
        if ctx.cancel.is_cancelled:
            return Result(None, (*built.diagnostics, CANCELLED))
        return Result(None if built.value is None else built.value.region, built.diagnostics)
    tree = loop_tree(loops, ctx)
    diagnostics = list(tree.diagnostics)
    if tree.value is None or not tree.ok:
        return Result(None, tuple(diagnostics))
    flat_region = flatten_loops(tree.value, kind, ctx)
    original = flat_region.region  # the input edges whose IDs the output takes (DEC-OFF-013)
    flat, cleaned = _cleaned(original, ctx)
    diagnostics += cleaned
    tol = ctx.tolerances
    # The flattening's extra clearance (0 for lines and arcs) widens t (geometry2d, REQ-G2D-124).
    t_mm = clearance_mm + flat_region.extra_clearance_mm
    reach = t_mm + tol.arc_tol_mm + BIAS_GRID_UNITS * tol.grid_unit_mm
    delta = -reach if kind is RegionKind.AIR else reach
    if flat.loop_starts.size == 0:  # every loop dropped by the loop tree
        status, region = OK, flat
    elif ctx.cancel.is_cancelled:
        return Result(None, (*diagnostics, CANCELLED))
    else:
        status, region = _kernel_offset(flat, original, classes, delta, ctx)
    return outcome(status, region, _replay_dump(original, delta, ctx), diagnostics, ctx)


def _check_arguments(
    loops: CurveRows, kind: RegionKind, clearance_mm: float, classes: SourceClasses, ctx: Context
) -> None:
    if kind not in tuple(RegionKind):  # a caller without type checks
        raise ValueError(f"the kind must be a RegionKind, got {kind!r}")
    if not (math.isfinite(clearance_mm) and clearance_mm >= 0.0):
        raise ValueError(f"the clearance must be finite and >= 0, got {clearance_mm!r}")
    check_classes(classes, loops.ids)
    if ctx.tolerances.arc_tol_mm < _ARC_TOL_FLOOR_GRID_UNITS * ctx.tolerances.grid_unit_mm:
        raise ValueError("the arc tolerance a must be at least 2 grid units")


def _cleaned(region: PolygonRegion, ctx: Context) -> tuple[PolygonRegion, list[Diagnostic]]:
    """Each flattened loop cleaned (geometry2d's `cleanup`: runs within eps_len merged, spikes
    dropped), for the geometry only (REQ-OFF-043, trap 9): the IDs come from the loops before."""
    starts_in: list[int] = region.loop_starts.tolist()
    ends = [*starts_in[1:], region.points.shape[0]] if starts_in else []
    kept: list[NDArray[np.int64]] = []
    diagnostics: list[Diagnostic] = []
    for start, end in zip(starts_in, ends, strict=True):
        result = cleanup(region.points[start:end], ctx)
        diagnostics += result.diagnostics
        assert result.value is not None  # cleanup always returns the kept indices
        kept.append(start + result.value)
    take = np.concatenate(kept) if kept else np.empty(0, dtype=np.int64)
    starts = np.cumsum([0, *[k.size for k in kept]], dtype=np.int64)[:-1]
    cleaned = PolygonRegion(
        region.points[take], starts, region.source_ids[take], region.fixed[take]
    )
    return cleaned, diagnostics


def _kernel_offset(
    flat: PolygonRegion,
    original: PolygonRegion,
    classes: SourceClasses,
    delta: float,
    ctx: Context,
) -> tuple[int, PolygonRegion | None]:
    """The cleaned loops offset, their IDs from the loops before the clean-up, which may drop a
    collinear joint between two rows (DEC-OFF-013)."""
    tol = ctx.tolerances
    offset = (delta, tol.arc_tol_mm, BIAS_GRID_UNITS, MARGIN_GRID_UNITS)
    grid = (tol.grid_unit_mm, MAX_SPAN_GRID_UNITS, JOIN_STEPS_MAX, tol.length_eps_mm)
    per_vertex = vertex_classes(classes, original.source_ids)
    # Room for the round joins: π / acos(1 - a/|δ|) steps per turn (Clipper2's DoRound), a turn
    # per loop at least; the kernel says when it needed more, and runs again.
    steps = math.pi / math.acos(1.0 - tol.arc_tol_mm / abs(delta))
    room = 2 * flat.points.shape[0] + math.ceil(steps) * (flat.loop_starts.size + 1) + 64

    def call(
        points: NDArray[np.float64],
        starts: NDArray[np.int64],
        ids: NDArray[np.int64],
        fixed: NDArray[np.uint8],
    ) -> tuple[int, int, int]:
        return _kernels.offset2d.offset_loops(
            flat.points, flat.loop_starts, original.points, original.loop_starts,
            original.source_ids, per_vertex, offset, grid, points, starts, ids, fixed,
        )  # fmt: skip

    return run_kernel(call, room)


def _replay_dump(flat: PolygonRegion, delta: float, ctx: Context) -> dict[str, object]:
    """The kernel's input as JSON-ready values, for `tools/replay` once it exists (REQ-OFF-014)."""
    return {
        "points": flat.points.tolist(),
        "loop_starts": flat.loop_starts.tolist(),
        "source_ids": flat.source_ids.tolist(),
        "delta_mm": delta,
        "arc_tol_mm": ctx.tolerances.arc_tol_mm,
        "bias_grid_units": BIAS_GRID_UNITS,
        "grid_unit_mm": ctx.tolerances.grid_unit_mm,
        "max_span_grid_units": MAX_SPAN_GRID_UNITS,
        "join_steps_max": JOIN_STEPS_MAX,
    }
