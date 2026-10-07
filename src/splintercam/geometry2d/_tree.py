# SPDX-License-Identifier: Apache-2.0
"""The loop tree: parents by containment probes, depths and normalised orientation (research 01,
Loop tree, rules 5 and 6)."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._distances import polyline_distances
from ._loops import LoopTree
from ._region import PointLocation, point_in_region
from ._rows import CurveRows
from ._screen import Screened, screen_loops

_ONE_LOOP = np.zeros(1, np.int64)


@dataclass(frozen=True, slots=True)
class Containment:
    """Whether B lies in A, and whether a probe decided it (else the rule 5 fallback would)."""

    contained: bool
    by_probe: bool


def _projections(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """Each vertex of a projected onto the nearest segment of closed polyline b (rule 5)."""
    start, d = b, np.roll(b, -1, axis=0) - b
    t = np.clip(((a[:, None, :] - start) * d).sum(axis=2) / (d * d).sum(axis=1), 0.0, 1.0)
    feet = start + t[..., None] * d
    nearest = np.argmin(((a[:, None, :] - feet) ** 2).sum(axis=2), axis=1)  # lowest index on ties
    return feet[np.arange(a.shape[0]), nearest]


def contains(
    b: NDArray[np.float64], a: NDArray[np.float64], a_rows: CurveRows, ctx: Context
) -> Containment:
    """B ⊂ A by the first probe of B farther than t_topo from A's flattening, among B's vertices,
    the midpoints of its segments and the projections of A's vertices onto B (REQ-G2D-168),
    located against A's exact rows alone (REQ-G2D-153, 167). Without such a probe the answer is
    "not contained", provisional until the rule 5 fallback (DEC-G2D-032).
    """
    t_topo = ctx.tolerances.topology_tol_mm
    groups = (b, (b + np.roll(b, -1, axis=0)) / 2, None)
    for group in groups:
        candidates = _projections(a, b) if group is None else group
        far = np.flatnonzero(np.isinf(polyline_distances(candidates, a, _ONE_LOOP, t_topo)))
        if far.size > 0:
            location = point_in_region(candidates[far[:1]], a_rows, ctx)[0]
            return Containment(bool(location == PointLocation.IN), True)
    return Containment(False, False)


Decision = Literal["a in b", "b in a", "apart", "cross"]


def both_ways(a_in_b: Containment, b_in_a: Containment) -> Decision:
    """The containment of two loops tested both ways (REQ-G2D-166): a probe's result stands over
    the fallback's (REQ-G2D-170); two probes finding each in the other mean the loops cross
    (REQ-G2D-173)."""
    if a_in_b.contained and b_in_a.contained:
        if a_in_b.by_probe and b_in_a.by_probe:
            return "cross"
        return "a in b" if a_in_b.by_probe else "b in a"
    if a_in_b.contained:
        return "a in b"
    return "b in a" if b_in_a.contained else "apart"


def _loop_rows(loops: CurveRows, i: int) -> CurveRows:
    end = int(loops.row_starts[i + 1]) if i + 1 < loops.row_starts.size else loops.rows.shape[0]
    first = int(loops.row_starts[i])
    return CurveRows(loops.rows[first:end], loops.ids[first:end], _ONE_LOOP)


def _containers(
    screened: Screened, loops: CurveRows, ctx: Context
) -> tuple[list[list[int]], list[Diagnostic]]:
    """Per kept loop the kept loops containing it (rule 5), and a `LOOPS_CROSS` per pair that
    contains each other by two probes."""
    t_topo = ctx.tolerances.topology_tol_mm
    polys, kept = screened.polylines, screened.kept.tolist()
    size = np.abs(screened.areas)
    boxes = np.array([[*p.min(axis=0), *p.max(axis=0)] for p in polys]).reshape(-1, 4)
    rows = [_loop_rows(loops, i) for i in kept]
    containers: list[list[int]] = [[] for _ in kept]
    notes: list[Diagnostic] = []
    for a in range(len(kept)):
        for b in range(a + 1, len(kept)):
            if np.any(boxes[a, :2] > boxes[b, 2:]) or np.any(boxes[b, :2] > boxes[a, 2:]):
                continue
            band = t_topo * (screened.lengths[a] + screened.lengths[b])
            if abs(size[a] - size[b]) <= band:
                decision = both_ways(
                    contains(polys[a], polys[b], rows[b], ctx),
                    contains(polys[b], polys[a], rows[a], ctx),
                )
            elif size[a] > size[b]:
                decision = (
                    "b in a" if contains(polys[b], polys[a], rows[a], ctx).contained else "apart"
                )
            else:
                decision = (
                    "a in b" if contains(polys[a], polys[b], rows[b], ctx).contained else "apart"
                )
            if decision == "a in b":
                containers[a].append(b)
            elif decision == "b in a":
                containers[b].append(a)
            elif decision == "cross":
                where = f"loops {kept[a]} and {kept[b]}"
                message = f"{where} each contain the other by a probe"
                notes.append(Diagnostic("LOOPS_CROSS", Severity.ERROR, message, where))
    return containers, notes


def _reversed(rows: CurveRows) -> CurveRows:
    """The loop the other way round: rows in reverse order, ends swapped, sweeps negated."""
    r = rows.rows[::-1]
    flipped = np.column_stack([r[:, 2:4], r[:, 0:2], r[:, 4:6], -r[:, 6]])
    return CurveRows(flipped, rows.ids[::-1].copy(), _ONE_LOOP)


def _empty_tree(screened: Screened) -> LoopTree:
    empty = CurveRows(np.empty((0, 7)), np.empty(0, np.int64), np.empty(0, np.int64))
    none = np.empty(0, np.int64)
    return LoopTree(empty, none, none, none, screened.crossing_points, screened.crossing_loops)


def loop_tree(loops: CurveRows, ctx: Context) -> Result[LoopTree]:
    """Closed loops of lines and arcs checked and nested: degenerate, duplicate and crossing loops
    reported (rules 1 to 4), each kept loop's parent and depth by containment probes (rule 5), and
    its orientation normalised, even depth CCW and odd depth CW (rule 6). When any loops cross, the
    tree holds no loops, only the crossings, with `LOOPS_CROSS` (REQ-G2D-162).

    Implements: REQ-G2D-151, REQ-G2D-153, REQ-G2D-154, REQ-G2D-162, REQ-G2D-164 to 168,
    REQ-G2D-170, REQ-G2D-173 to 175.
    """
    screened_result = screen_loops(loops, ctx)
    screened = screened_result.value
    if screened is None:  # screen_loops always returns its loops
        raise RuntimeError("screen_loops returned no value")
    diagnostics = list(screened_result.diagnostics)
    if screened.crossing_points.shape[0] > 0:
        return Result(_empty_tree(screened), tuple(diagnostics))
    containers, notes = _containers(screened, loops, ctx)
    if notes:
        return Result(_empty_tree(screened), (*diagnostics, *notes))
    size = np.abs(screened.areas)
    # The parent lies inside every other container: the smallest one, the lower index on a tie.
    parent = [min(c, key=lambda a: (size[a], a)) if c else -1 for c in containers]
    depth: list[int] = []
    for b in range(len(parent)):
        d, up = 0, parent[b]
        while up >= 0:
            d, up = d + 1, parent[up]
        depth.append(d)
    pieces: list[CurveRows] = []
    for position, i in enumerate(screened.kept.tolist()):
        rows = _loop_rows(loops, i)
        ccw = screened.areas[position] > 0
        pieces.append(rows if ccw == (depth[position] % 2 == 0) else _reversed(rows))
    sizes = [p.rows.shape[0] for p in pieces]
    normalised = CurveRows(
        np.vstack([p.rows for p in pieces]) if pieces else np.empty((0, 7)),
        np.concatenate([p.ids for p in pieces]) if pieces else np.empty(0, np.int64),
        np.cumsum([0, *sizes[:-1]], dtype=np.int64) if pieces else np.empty(0, np.int64),
    )
    for array in (normalised.rows, normalised.ids, normalised.row_starts):
        array.flags.writeable = False
    tree = LoopTree(
        normalised,
        np.array(parent, dtype=np.int64),
        np.array(depth, dtype=np.int64),
        screened.kept,
        screened.crossing_points,
        screened.crossing_loops,
    )
    return Result(tree, tuple(diagnostics))
