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
    OK,
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
    """One side of an open chain (REQ-OFF-028): the pieces one after another; an open piece runs in
    the chain's direction, from the cap at its start to the cap at its end, with one source ID per
    edge; a closed piece keeps its loop's traversal, its closing edge implied, one ID per vertex."""

    points: NDArray[np.float64]  # (n, 2)
    starts: NDArray[np.int64]  # (k,), first vertex of each piece
    closed: NDArray[np.bool_]  # (k,)
    source_ids: NDArray[np.int64]  # one per edge: (n - open pieces,)
    fixed: NDArray[np.uint8]  # (n,)


@dataclass(frozen=True, slots=True)
class _Side:
    """The flattened chain and what the kernel call of one side takes besides."""

    points: NDArray[np.float64]
    source_ids: NDArray[np.int64]
    tool: int  # +1 left, -1 right
    delta: float


def offset_chain_side(  # noqa: PLR0913 (the SPEC's reviewed interface, DEC-OFF-004, DEC-OFF-018)
    rows: NDArray[np.float64],
    ids: NDArray[np.int64],
    tool_side: AirSide,
    clearance_mm: float,
    classes: SourceClasses,
    ctx: Context,
) -> Result[OpenPaths]:
    """The tool-centre path at clearance t on one side of an open chain (a profile, D-025): the
    chain flattened with the tool's side as the air side of every arc, offset with flat ends by
    δ = t + a + 3u, and of that area's boundary the edges on the tool side, the caps at the
    chain's ends left out (research 02, Open chains). A closed chain is refused with
    `CHAIN_CLOSED`; an empty result carries `OFFSET_EMPTY`.

    Implements: REQ-OFF-013, REQ-OFF-028, REQ-OFF-029, REQ-OFF-031.
    """
    _check_side_arguments(ids, tool_side, clearance_mm, classes, ctx)
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    chain = build_chain(rows, ids, tool_side, ctx)  # the tool's side is the arcs' air side
    if chain.value is None:
        return Result(None, chain.diagnostics)
    points = chain.value.points
    early = _degenerate(points, list(chain.diagnostics))
    if early is not None:
        return early
    tol = ctx.tolerances
    delta = clearance_mm + tol.arc_tol_mm + BIAS_GRID_UNITS * tol.grid_unit_mm
    tool = 1 if tool_side is AirSide.LEFT else -1
    side = _Side(points, chain.value.source_ids, tool, delta)
    return _run_side(side, classes, list(chain.diagnostics), ctx)


def _check_side_arguments(
    ids: NDArray[np.int64],
    tool_side: AirSide,
    clearance_mm: float,
    classes: SourceClasses,
    ctx: Context,
) -> None:
    if tool_side not in tuple(AirSide):  # a caller without type checks
        raise ValueError(f"the tool side must be an AirSide, got {tool_side!r}")
    if not (math.isfinite(clearance_mm) and clearance_mm > 0.0):
        raise ValueError(f"the clearance must be finite and > 0, got {clearance_mm!r}")
    check_classes(classes, np.asarray(ids, dtype=np.int64))
    check_arc_tol(ctx)


def _degenerate(
    points: NDArray[np.float64], diagnostics: list[Diagnostic]
) -> Result[OpenPaths] | None:
    """A closed chain (`CHAIN_CLOSED`) or one of zero length, which has no side (`OFFSET_EMPTY`);
    None for a chain to offset."""
    if closes(points):
        message = "the chain closes: a loop goes through offset_region"
        diagnostics.append(Diagnostic("CHAIN_CLOSED", Severity.ERROR, message))
        return Result(None, tuple(diagnostics))
    if points.shape[0] < 2:
        message = "a chain of zero length has no side"
        diagnostics.append(Diagnostic("OFFSET_EMPTY", Severity.INFO, message))
        return Result(_no_paths(), tuple(diagnostics))
    return None


def _run_side(
    side: _Side, classes: SourceClasses, diagnostics: list[Diagnostic], ctx: Context
) -> Result[OpenPaths]:
    status, paths = _side_kernel(side, classes, ctx)
    if ctx.cancel.is_cancelled:
        return Result(None, (*diagnostics, CANCELLED))
    if status != OK or paths is None:

        def dump() -> dict[str, object]:
            return {"chain": side.points.tolist(), "delta_mm": side.delta, "tool": side.tool}

        failed = outcome(status, None, dump, diagnostics, ctx)
        return Result(None, failed.diagnostics)
    if paths.starts.size == 0:
        diagnostics.append(Diagnostic("OFFSET_EMPTY", Severity.INFO, "the side vanishes"))
    return Result(paths, tuple(diagnostics))


def _no_paths() -> OpenPaths:
    return OpenPaths(
        np.empty((0, 2)), np.empty(0, np.int64), np.empty(0, bool), np.empty(0, np.int64),
        np.empty(0, np.uint8),
    )  # fmt: skip


def _side_kernel(side: _Side, classes: SourceClasses, ctx: Context) -> tuple[int, OpenPaths | None]:
    """The kernel call, with the chain there and back for the IDs (DEC-OFF-015)."""
    tol = ctx.tolerances
    points, source_ids = side.points, side.source_ids
    id_points = np.concatenate([points, points[-2:0:-1]])
    ids = np.concatenate([source_ids, source_ids[-1:], source_ids[-2::-1]]).astype(np.int64)
    per_vertex = vertex_classes(classes, ids)
    reach = side.delta + MARGIN_GRID_UNITS * tol.grid_unit_mm
    offset = (side.delta, tol.arc_tol_mm, reach, BIAS_GRID_UNITS)
    grid = (tol.grid_unit_mm, MAX_SPAN_GRID_UNITS, JOIN_STEPS_MAX, tol.length_eps_mm)
    steps = math.pi / math.acos(1.0 - tol.arc_tol_mm / side.delta)
    room = 4 * points.shape[0] + math.ceil(steps) + 64
    chain = np.ascontiguousarray(points, dtype=np.float64)
    id_starts = np.array([0], dtype=np.int64)
    while True:
        out = _SideOut(room)
        status, n_points, n_pieces, n_ids = _kernels.offset2d.chain_side(
            chain, id_points, id_starts, ids, per_vertex, side.tool, offset, grid,
            out.points, out.starts, out.closed, out.ids, out.fixed,
        )  # fmt: skip
        if max(n_points, n_pieces, n_ids) <= room:
            break
        room = max(n_points, n_pieces, n_ids)
    if status != OK:
        return status, None
    return status, out.ordered(n_points, n_pieces)


class _SideOut:
    """The arrays the kernel writes the pieces into."""

    def __init__(self, room: int) -> None:
        self.points: NDArray[np.float64] = np.empty((room, 2))
        self.starts: NDArray[np.int64] = np.empty(room, dtype=np.int64)
        self.closed: NDArray[np.uint8] = np.empty(room, dtype=np.uint8)
        self.ids: NDArray[np.int64] = np.empty(room, dtype=np.int64)
        self.fixed: NDArray[np.uint8] = np.empty(room, dtype=np.uint8)

    def ordered(self, n_points: int, n_pieces: int) -> OpenPaths:
        """The pieces sorted by their first vertex, x then y (REQ-OFF-038, ours), read-only."""
        starts: list[int] = self.starts[:n_pieces].tolist()
        closed: list[bool] = [bool(c) for c in self.closed[:n_pieces].tolist()]
        ends = [*starts[1:], n_points]
        id_counts = [e - s - (0 if c else 1) for s, e, c in zip(starts, ends, closed, strict=True)]
        id_starts = [sum(id_counts[:k]) for k in range(n_pieces)]
        first: list[tuple[float, float]] = [
            (float(self.points[s, 0]), float(self.points[s, 1])) for s in starts
        ]
        order = sorted(range(n_pieces), key=lambda k: first[k])
        take = [np.arange(starts[k], ends[k], dtype=np.int64) for k in order]
        take_ids = [
            np.arange(id_starts[k], id_starts[k] + id_counts[k], dtype=np.int64) for k in order
        ]
        vertices = np.concatenate(take) if take else np.empty(0, np.int64)
        edges = np.concatenate(take_ids) if take_ids else np.empty(0, np.int64)
        sizes = [ends[k] - starts[k] for k in order]
        result = OpenPaths(
            self.points[vertices],
            np.cumsum([0, *sizes], dtype=np.int64)[:-1],
            np.array([closed[k] for k in order], dtype=bool),
            self.ids[edges],
            self.fixed[vertices],
        )
        for array in (result.points, result.starts, result.closed, result.source_ids, result.fixed):
            array.flags.writeable = False
        return result
