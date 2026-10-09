# SPDX-License-Identifier: Apache-2.0
"""The region offset (research 02, Definitions and The kernel call): a region of air shrinks, a
region of material grows by a clearance t, in one Clipper2 call on geometry2d's grid."""

import json
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
    Severity,
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

# Declared parameters, passed to the kernel as plain values (REQ-OFF-042, D-049).
_BIAS_GRID_UNITS = TOLERANCE_DEFAULTS["offset_bias_grid_units"].default  # D-132
_MARGIN_GRID_UNITS = TOLERANCE_DEFAULTS["rounding_margin_grid_units"].default  # D-132
_JOIN_STEPS_MAX = TOLERANCE_DEFAULTS["join_steps_max"].default  # research 02, Parameters
_MAX_SPAN_GRID_UNITS = TOLERANCE_DEFAULTS["grid_max_span_units"].default  # REQ-G2D-034
_ARC_TOL_FLOOR_GRID_UNITS = TOLERANCE_DEFAULTS["arc_tol_floor_grid_units"].default  # D-132
_OK, _TOO_LARGE = 0, 1  # GridStatus in geometry2d's kernel/grid.hpp; 2 is a failure


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
    REQ-OFF-039 to 043; REQ-OFF-034 provisionally (the lower index on a tie, DEC-OFF-009).
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
    flat, cleaned = _cleaned(flat_region.region, ctx)
    diagnostics += cleaned
    tol = ctx.tolerances
    # The flattening's extra clearance (0 for lines and arcs) widens t (geometry2d, REQ-G2D-124).
    t_mm = clearance_mm + flat_region.extra_clearance_mm
    reach = t_mm + tol.arc_tol_mm + _BIAS_GRID_UNITS * tol.grid_unit_mm
    delta = -reach if kind is RegionKind.AIR else reach
    if flat.loop_starts.size == 0:  # every loop dropped by the loop tree
        status, region = _OK, flat
    elif ctx.cancel.is_cancelled:
        return Result(None, (*diagnostics, CANCELLED))
    else:
        status, region = _kernel_offset(flat, delta, ctx)
    return _outcome(status, region, (flat, delta), diagnostics, ctx)


def _outcome(
    status: int,
    region: PolygonRegion | None,
    kernel_input: tuple[PolygonRegion, float],
    diagnostics: list[Diagnostic],
    ctx: Context,
) -> Result[PolygonRegion]:
    """The kernel's status as a result: cancelled, refused, failed (the input logged), empty or
    the region (REQ-OFF-014, 018, 039, 041)."""
    if ctx.cancel.is_cancelled:
        return Result(None, (*diagnostics, CANCELLED))
    if status == _TOO_LARGE:
        message = f"the input plus 2·|δ| spans {_MAX_SPAN_GRID_UNITS:.0f} grid units or more"
        return Result(None, (*diagnostics, Diagnostic("REGION_TOO_LARGE", Severity.ERROR, message)))
    if status != _OK or region is None:
        _log_for_replay(*kernel_input, ctx)
        failed = Diagnostic("OFFSET_FAILED", Severity.ERROR, "the offset failed; input logged")
        return Result(None, (*diagnostics, failed))
    if region.loop_starts.size == 0:
        diagnostics.append(Diagnostic("OFFSET_EMPTY", Severity.INFO, "the region vanishes"))
    return Result(region, tuple(diagnostics))


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
    dropped), its kept vertices keeping their source IDs (REQ-OFF-043, trap 9)."""
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
    flat: PolygonRegion, delta: float, ctx: Context
) -> tuple[int, PolygonRegion | None]:
    tol = ctx.tolerances
    offset = (delta, tol.arc_tol_mm, _BIAS_GRID_UNITS, _MARGIN_GRID_UNITS)
    grid = (tol.grid_unit_mm, _MAX_SPAN_GRID_UNITS, _JOIN_STEPS_MAX)
    # Room for the round joins: π / acos(1 - a/|δ|) steps per turn (Clipper2's DoRound), a turn
    # per loop at least; the kernel says when it needed more, and runs again.
    steps = math.pi / math.acos(1.0 - tol.arc_tol_mm / abs(delta))
    room = 2 * flat.points.shape[0] + math.ceil(steps) * (flat.loop_starts.size + 1) + 64
    while True:
        points, starts = np.empty((room, 2)), np.empty(room, dtype=np.int64)
        ids, fixed = np.empty(room, dtype=np.int64), np.empty(room, dtype=np.uint8)
        status, n_points, n_loops = _kernels.offset2d.offset_loops(
            flat.points, flat.loop_starts, flat.source_ids, offset, grid,
            points, starts, ids, fixed,
        )  # fmt: skip
        if max(n_points, n_loops) <= room:
            break
        room = max(n_points, n_loops)
    if status != _OK:
        return status, None
    out = PolygonRegion(
        points[:n_points].copy(), starts[:n_loops].copy(), ids[:n_points].copy(),
        fixed[:n_points].copy(),
    )  # fmt: skip
    for array in (out.points, out.loop_starts, out.source_ids, out.fixed):
        array.flags.writeable = False
    return status, out


def _log_for_replay(flat: PolygonRegion, delta: float, ctx: Context) -> None:
    """The kernel's input as JSON, for `tools/replay` once it exists (REQ-OFF-014)."""
    dump = {
        "points": flat.points.tolist(),
        "loop_starts": flat.loop_starts.tolist(),
        "source_ids": flat.source_ids.tolist(),
        "delta_mm": delta,
        "arc_tol_mm": ctx.tolerances.arc_tol_mm,
        "bias_grid_units": _BIAS_GRID_UNITS,
        "grid_unit_mm": ctx.tolerances.grid_unit_mm,
        "max_span_grid_units": _MAX_SPAN_GRID_UNITS,
        "join_steps_max": _JOIN_STEPS_MAX,
    }
    ctx.logger.error("OFFSET_FAILED, kernel input for replay: %s", json.dumps(dump))
