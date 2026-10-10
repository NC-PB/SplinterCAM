# SPDX-License-Identifier: Apache-2.0
"""Open chains grown on both sides (research 02, Open chains): for link checks (D-062) and, through
`grow_flat_chains`, for the machined area of the stock update."""

import math
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity
from splintercam.geometry2d import AirSide, PolygonRegion, build_chain, orient2d

from ._classes import SourceClasses, check_classes
from ._results import (
    BIAS_GRID_UNITS,
    JOIN_STEPS_MAX,
    MARGIN_GRID_UNITS,
    MAX_SPAN_GRID_UNITS,
    check_arc_tol,
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
    check_arc_tol(ctx)
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    chain = build_chain(rows, ids, AirSide.LEFT, ctx)  # either side: δ adds t_flat
    if chain.value is None:
        return Result(None, chain.diagnostics)
    points = chain.value.points
    if closes(points):
        message = "the chain closes: a loop goes through offset_region"
        return Result(
            None, (*chain.diagnostics, Diagnostic("CHAIN_CLOSED", Severity.ERROR, message))
        )
    tol = ctx.tolerances
    delta = clearance_mm + tol.flatten_tol_mm + tol.arc_tol_mm + BIAS_GRID_UNITS * tol.grid_unit_mm
    # The boundary lies within [t, t + t_flat + a + 6u] of the flattened chain, δ + 3u at most, so
    # δ plus the rounding margin reaches the source edge of every output edge's middle.
    reach = delta + MARGIN_GRID_UNITS * tol.grid_unit_mm
    flat = [flat_chain(points, chain.value.source_ids, np.asarray(ids, dtype=np.int64))]
    status, region = grow_flat_chains(flat, delta, reach, classes, ctx)

    def dump() -> dict[str, object]:
        return {"chain": points.tolist(), "delta_mm": delta, "arc_tol_mm": tol.arc_tol_mm,
                "grid_unit_mm": tol.grid_unit_mm}  # fmt: skip

    return outcome(status, region, dump, list(chain.diagnostics), ctx)


def closes(points: NDArray[np.float64]) -> bool:
    """Whether a flattened chain is a loop: its ends meet and it encloses an area, so its points
    are not all on one line (geometry2d's exact `orient2d`). A chain out and back (A to B to A)
    or of zero length is open (DEC-OFF-017)."""
    if points.shape[0] < 3 or not bool(np.all(points[0] == points[-1])):
        return False
    other = np.flatnonzero(np.any(points != points[0], axis=1))
    if other.size == 0:
        return False
    n = points.shape[0]
    first, second = np.repeat(points[:1], n, axis=0), np.repeat(points[other[:1]], n, axis=0)
    return bool(np.any(orient2d(first, second, points) != 0))


def flat_chain(
    points: NDArray[np.float64], source_ids: NDArray[np.int64], row_ids: NDArray[np.int64]
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """A flattened chain for `grow_flat_chains`; a chain of zero length (a plunge seen from above,
    a single point) becomes a segment of length 0 with its row's ID, which grows into a disc."""
    if points.shape[0] == 1:
        return np.vstack([points, points]), row_ids[:1].astype(np.int64)
    return points, source_ids


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


@dataclass(frozen=True, slots=True)
class OpenPaths:
    """One side of an open chain (REQ-OFF-028): the open pieces along the chain, each from the cap
    at its start to the cap at its end with one source ID per edge, then the closed pieces, each
    with its closing edge implied and one ID per vertex. Every piece runs with the chain on the
    side away from the tool, so all share one milling direction (DEC-OFF-020); a piece the first
    open piece cannot reach without cutting closer than t is enclosed (DEC-OFF-019)."""

    points: NDArray[np.float64]  # (n, 2)
    starts: NDArray[np.int64]  # (k,), first vertex of each piece
    closed: NDArray[np.bool_]  # (k,)
    enclosed: NDArray[np.bool_]  # (k,), on another boundary loop than the first open piece
    source_ids: NDArray[np.int64]  # one per edge: (n - open pieces,)
    fixed: NDArray[np.uint8]  # (n,)


def offset_chain_side(  # noqa: PLR0913 (the SPEC's reviewed interface, DEC-OFF-004, DEC-OFF-018)
    rows: NDArray[np.float64],
    ids: NDArray[np.int64],
    tool_side: AirSide,
    clearance_mm: float,
    classes: SourceClasses,
    ctx: Context,
) -> Result[OpenPaths]:
    """The tool-centre path at clearance t on one side of an open chain (a profile, D-025): the
    chain flattened with the tool's side as the air side of every arc, grown with round ends by
    δ = t + a + 3u, and of that area's boundary the edges on the tool side, the round caps at the
    chain's ends left out (research 02, Open chains; DEC-OFF-018). A closed chain is refused with
    `CHAIN_CLOSED`; an empty result carries `OFFSET_EMPTY`.

    Implements: REQ-OFF-013, REQ-OFF-018, REQ-OFF-028, REQ-OFF-029.
    """
    if tool_side not in tuple(AirSide):  # a caller without type checks
        raise ValueError(f"the tool side must be an AirSide, got {tool_side!r}")
    if not (math.isfinite(clearance_mm) and clearance_mm > 0.0):
        raise ValueError(f"the clearance must be finite and > 0, got {clearance_mm!r}")
    check_classes(classes, np.asarray(ids, dtype=np.int64))
    check_arc_tol(ctx)
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    chain = build_chain(rows, ids, tool_side, ctx)  # the tool's side is the arcs' air side
    if chain.value is None:
        return Result(None, chain.diagnostics)
    diagnostics = list(chain.diagnostics)
    tol = ctx.tolerances
    # Below the grid unit the grown area cannot show a segment, so the labels must not see it.
    threshold = max(tol.grid_unit_mm, tol.length_eps_mm)
    points, source_ids = merge_short(chain.value.points, chain.value.source_ids, threshold)
    refusal = _refusal(chain.value.points, points)
    if refusal is not None:
        return Result(None, (*diagnostics, refusal))
    if points.shape[0] < 2:
        message = "a chain of zero length has no side"
        empty = Diagnostic("OFFSET_EMPTY", Severity.INFO, message)
        return Result(_paths(None, _SideOut()), (*diagnostics, empty))
    delta = clearance_mm + tol.arc_tol_mm + BIAS_GRID_UNITS * tol.grid_unit_mm
    side = _Side(points, source_ids, 1 if tool_side is AirSide.LEFT else -1, delta)
    return _offset_side(side, classes, diagnostics, ctx)


def merge_short(
    points: NDArray[np.float64], source_ids: NDArray[np.int64], threshold: float
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """The chain with its points within `threshold` of the last kept one merged away (the ends
    stay, no point moves), so no segment is threshold or shorter; a merged segment takes the ID
    of its longest part (DEC-OFF-018). A chain shorter than that is one point."""
    keep = np.empty(points.shape[0], dtype=np.uint8)
    _kernels.offset2d.keep_chain(np.ascontiguousarray(points, dtype=np.float64), threshold, keep)
    kept = keep.astype(bool)
    if points.shape[0] < 2 or int(np.count_nonzero(kept)) == points.shape[0]:
        return points, source_ids
    if int(np.count_nonzero(kept)) == 2 and _length(points[kept])[0] <= threshold:
        return points[:1], source_ids[:0]
    length = _length(points)
    group = np.cumsum(kept[:-1]) - 1
    order = np.lexsort((-length, group))
    first = order[np.r_[True, group[order][1:] != group[order][:-1]]]
    return points[kept], source_ids[first]


def _length(points: NDArray[np.float64]) -> NDArray[np.float64]:
    d = np.diff(points, axis=0)
    return np.sqrt(d[:, 0] * d[:, 0] + d[:, 1] * d[:, 1])  # not hypot (geometry2d, local rules)


def _refusal(flat: NDArray[np.float64], merged: NDArray[np.float64]) -> Diagnostic | None:
    """`CHAIN_CLOSED` for a loop; `CHAIN_FOLDS` where the merged chain turns back on itself at a
    vertex (exactly collinear, by geometry2d's `orient2d`), which leaves it no side (DEC-OFF-018,
    provisional)."""
    if closes(flat):
        message = "the chain closes: a loop goes through offset_region"
        return Diagnostic("CHAIN_CLOSED", Severity.ERROR, message)
    if merged.shape[0] < 3:
        return None
    before, corner, after = merged[:-2], merged[1:-1], merged[2:]
    dot = ((corner - before) * (after - corner)).sum(axis=1)
    back = np.flatnonzero((orient2d(before, corner, after) == 0) & (dot < 0.0))
    if back.size == 0:
        return None
    x, y = (float(v) for v in corner[back[0]])
    return _folds(x, y)


def _folds(x: float, y: float) -> Diagnostic:
    message = "the chain runs back over itself, so it has no side there"
    return Diagnostic("CHAIN_FOLDS", Severity.ERROR, message, f"({x:.4f}, {y:.4f}) mm")


@dataclass(frozen=True, slots=True)
class _Side:
    """The merged chain and what the kernel call of one side takes besides."""

    points: NDArray[np.float64]
    source_ids: NDArray[np.int64]
    tool: int  # +1 left, -1 right
    delta: float


@dataclass(slots=True)
class _SideOut:
    """What the kernel writes besides the region: each piece's flags (1 closed, 2 enclosed) and
    where the chain folds back over itself."""

    flags: NDArray[np.uint8] = field(default_factory=lambda: np.empty(0, np.uint8))
    fold: list[float] | None = None  # x, y


def _offset_side(
    side: _Side, classes: SourceClasses, diagnostics: list[Diagnostic], ctx: Context
) -> Result[OpenPaths]:
    """The kernel call, with the chain there and back for the IDs (DEC-OFF-015), as a result."""
    tol = ctx.tolerances
    points, source_ids = side.points, side.source_ids
    id_points = np.concatenate([points, points[-2:0:-1]])
    ids = np.concatenate([source_ids, source_ids[-1:], source_ids[-2::-1]]).astype(np.int64)
    per_vertex = vertex_classes(classes, ids)
    reach = side.delta + MARGIN_GRID_UNITS * tol.grid_unit_mm
    offset = (side.delta, tol.arc_tol_mm, reach, BIAS_GRID_UNITS)
    grid = (tol.grid_unit_mm, MAX_SPAN_GRID_UNITS, JOIN_STEPS_MAX, tol.length_eps_mm)
    steps = math.pi / math.acos(1.0 - tol.arc_tol_mm / side.delta)
    chain = np.ascontiguousarray(points, dtype=np.float64)
    out = _SideOut()

    def call(
        out_points: NDArray[np.float64],
        out_starts: NDArray[np.int64],
        out_ids: NDArray[np.int64],
        out_fixed: NDArray[np.uint8],
    ) -> tuple[int, int, int]:
        out.flags = np.empty(out_starts.size, dtype=np.uint8)
        status, n_points, n_pieces, out.fold = _kernels.offset2d.chain_side(
            chain, id_points, np.array([0], dtype=np.int64), ids, per_vertex, side.tool, offset,
            grid, out_points, out_starts, out.flags, out_ids, out_fixed,
        )  # fmt: skip
        return status, n_points, n_pieces

    status, region = run_kernel(call, 4 * points.shape[0] + 2 * math.ceil(steps) + 64)
    if out.fold is not None and not ctx.cancel.is_cancelled:
        return Result(None, (*diagnostics, _folds(out.fold[0], out.fold[1])))

    def dump() -> dict[str, object]:
        return {"chain": points.tolist(), "delta_mm": side.delta, "tool": side.tool,
                "arc_tol_mm": tol.arc_tol_mm, "grid_unit_mm": tol.grid_unit_mm}  # fmt: skip

    result = outcome(status, region, dump, diagnostics, ctx)
    if result.value is None:
        return Result(None, result.diagnostics)
    return Result(_paths(result.value, out), result.diagnostics)


def _paths(region: PolygonRegion | None, out: _SideOut) -> OpenPaths:
    """The pieces of the kernel's region as open paths, read-only; no pieces for None."""
    if region is None:
        none = np.empty(0, bool)
        return OpenPaths(
            np.empty((0, 2)), np.empty(0, np.int64), none, none, np.empty(0, np.int64),
            np.empty(0, np.uint8),
        )  # fmt: skip
    k = region.loop_starts.size
    per_piece = out.flags[:k]
    closed, enclosed = (per_piece & 1).astype(bool), (per_piece & 2).astype(bool)
    n_ids = region.points.shape[0] - int(np.count_nonzero(~closed))
    paths = OpenPaths(
        region.points, region.loop_starts, closed, enclosed, region.source_ids[:n_ids], region.fixed
    )
    for array in (paths.closed, paths.enclosed, paths.source_ids):
        array.flags.writeable = False
    return paths
