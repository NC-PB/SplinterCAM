# SPDX-License-Identifier: Apache-2.0
"""Open chains grown on both sides (research 02, Open chains): for link checks (D-062) and, through
`grow_flat_chains`, for the machined area of the stock update."""

import math
from dataclasses import dataclass

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
    if closes(chain.value.points):
        message = "the chain closes: a loop goes through offset_region"
        return Result(None, (*diagnostics, Diagnostic("CHAIN_CLOSED", Severity.ERROR, message)))
    tol = ctx.tolerances
    points, source_ids = merge_short(chain.value.points, chain.value.source_ids, tol.length_eps_mm)
    if points.shape[0] < 2:
        message = "a chain of zero length has no side"
        return Result(
            _paths(None, 0), (*diagnostics, Diagnostic("OFFSET_EMPTY", Severity.INFO, message))
        )
    delta = clearance_mm + tol.arc_tol_mm + BIAS_GRID_UNITS * tol.grid_unit_mm
    tool = 1 if tool_side is AirSide.LEFT else -1
    status, region, flags = _side_kernel((points, source_ids), tool, delta, classes, ctx)

    def dump() -> dict[str, object]:
        return {"chain": points.tolist(), "delta_mm": delta, "tool": tool,
                "arc_tol_mm": tol.arc_tol_mm, "grid_unit_mm": tol.grid_unit_mm}  # fmt: skip

    result = outcome(status, region, dump, diagnostics, ctx)
    if result.value is None:
        return Result(None, result.diagnostics)
    return Result(_paths(result.value, flags), result.diagnostics)


def merge_short(
    points: NDArray[np.float64], source_ids: NDArray[np.int64], eps_len: float
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """The chain without segments of eps_len or shorter, so the side rule always sees two real
    segments at a vertex (DEC-OFF-018): a short segment's end merges away (its start, for the last
    one), the ends stay, and a merged segment takes the ID of its longest part."""
    while points.shape[0] > 2:
        length = np.hypot(*np.diff(points, axis=0).T)
        if not bool(np.any(length <= eps_len)):
            break
        keep = np.ones(points.shape[0], dtype=bool)
        keep[1:-1] = length[:-1] > eps_len
        keep[-2] &= length[-1] > eps_len
        group = np.cumsum(keep[:-1]) - 1
        order = np.lexsort((-length, group))
        first = order[np.r_[True, group[order][1:] != group[order][:-1]]]
        points, source_ids = points[keep], source_ids[first]
    if points.shape[0] == 2 and float(np.hypot(*(points[1] - points[0]))) <= eps_len:
        return points[:1], source_ids[:0]
    return points, source_ids


def _side_kernel(
    flat: tuple[NDArray[np.float64], NDArray[np.int64]],
    tool: int,
    delta: float,
    classes: SourceClasses,
    ctx: Context,
) -> tuple[int, PolygonRegion | None, NDArray[np.uint8]]:
    """The kernel call, with the chain there and back for the IDs (DEC-OFF-015); the pieces as a
    region and each piece's flags (1 closed, 2 enclosed)."""
    tol = ctx.tolerances
    points, source_ids = flat
    id_points = np.concatenate([points, points[-2:0:-1]])
    ids = np.concatenate([source_ids, source_ids[-1:], source_ids[-2::-1]]).astype(np.int64)
    per_vertex = vertex_classes(classes, ids)
    offset = (delta, tol.arc_tol_mm, delta + MARGIN_GRID_UNITS * tol.grid_unit_mm, BIAS_GRID_UNITS)
    grid = (tol.grid_unit_mm, MAX_SPAN_GRID_UNITS, JOIN_STEPS_MAX, tol.length_eps_mm)
    steps = math.pi / math.acos(1.0 - tol.arc_tol_mm / delta)
    chain = np.ascontiguousarray(points, dtype=np.float64)
    flags = [np.empty(0, np.uint8)]

    def call(
        out_points: NDArray[np.float64],
        out_starts: NDArray[np.int64],
        out_ids: NDArray[np.int64],
        out_fixed: NDArray[np.uint8],
    ) -> tuple[int, int, int]:
        flags[0] = np.empty(out_starts.size, dtype=np.uint8)
        return _kernels.offset2d.chain_side(
            chain, id_points, np.array([0], dtype=np.int64), ids, per_vertex, tool, offset, grid,
            out_points, out_starts, flags[0], out_ids, out_fixed,
        )  # fmt: skip

    status, region = run_kernel(call, 4 * points.shape[0] + 2 * math.ceil(steps) + 64)
    return status, region, flags[0]


def _paths(region: PolygonRegion | None, flags: NDArray[np.uint8] | int) -> OpenPaths:
    """The pieces of the kernel's region as open paths, read-only; no pieces for None."""
    if region is None:
        none = np.empty(0, bool)
        return OpenPaths(
            np.empty((0, 2)), np.empty(0, np.int64), none, none, np.empty(0, np.int64),
            np.empty(0, np.uint8),
        )  # fmt: skip
    k = region.loop_starts.size
    per_piece = np.asarray(flags, dtype=np.uint8)[:k]
    closed, enclosed = (per_piece & 1).astype(bool), (per_piece & 2).astype(bool)
    n_ids = region.points.shape[0] - int(np.count_nonzero(~closed))
    out = OpenPaths(
        region.points, region.loop_starts, closed, enclosed, region.source_ids[:n_ids], region.fixed
    )
    for array in (out.closed, out.enclosed, out.source_ids):
        array.flags.writeable = False
    return out
