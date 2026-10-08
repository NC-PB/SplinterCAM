# SPDX-License-Identifier: Apache-2.0
"""The loop tree: parents by containment probes, depths and normalised orientation (research 01,
Loop tree, rules 5 and 6)."""

import math

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._contain import nest
from ._crossings import pair_name
from ._loops import LoopTree
from ._rows import CurveRows
from ._screen import screen_loops

_ONE_LOOP = np.zeros(1, np.int64)


def _reversed(rows: CurveRows) -> CurveRows:
    """The loop the other way round: rows in reverse order, ends swapped, sweeps negated."""
    r = rows.rows[::-1]
    flipped = np.column_stack([r[:, 2:4], r[:, 0:2], r[:, 4:6], -r[:, 6]])
    return CurveRows(flipped, rows.ids[::-1].copy(), _ONE_LOOP)


def _empty_tree(points: NDArray[np.float64], pairs: NDArray[np.int64]) -> LoopTree:
    empty = CurveRows(np.empty((0, 7)), np.empty(0, np.int64), np.empty(0, np.int64))
    none = np.empty(0, np.int64)
    return LoopTree(empty, none, none, none, points, pairs)


def _overwound(kept: list[int], parents: list[int], areas: NDArray[np.float64]) -> list[int]:
    """The input loops whose pieces after their slits wind outside 0 and 1 (REQ-G2D-238): each
    piece's sign, flipped once per piece of its own loop around it, must agree (a hole drawn the
    other way round from its outer loop, a shape beside it the same way)."""
    signs: dict[int, set[float]] = {}
    for p, loop in enumerate(kept):
        around, q = 0, parents[p]
        while q >= 0:
            around += kept[q] == loop
            q = parents[q]
        signs.setdefault(loop, set()).add(math.copysign(1.0, areas[p]) * (-1.0) ** around)
    return sorted(loop for loop, found in signs.items() if len(found) > 1)


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
    crossings = (screened.crossing_points, screened.crossing_loops)
    if any(d.severity is Severity.ERROR for d in diagnostics):  # crossings or refusals, REQ-G2D-162
        return Result(_empty_tree(*crossings), tuple(diagnostics))
    kept = screened.kept.tolist()
    rows = list(screened.rows)
    nesting = nest(list(screened.polylines), screened.areas, screened.lengths, rows, ctx)
    parent, depth, crossing = nesting.parents, nesting.depths, nesting.crossing
    notes = [
        (
            kept[a],
            Diagnostic(
                "LOOPS_CROSS",
                Severity.ERROR,
                f"{'two pieces of ' if kept[a] == kept[b] else ''}{pair_name(kept[a], kept[b])} "
                "contain each other, or do not nest",
                pair_name(kept[a], kept[b]),
            ),
        )
        for a, b in crossing
    ]
    notes += [
        (
            kept[a],
            Diagnostic(code, Severity.ERROR, f"the containment fallback of {where} failed", where),
        )
        for a, b, code in nesting.refused
        for where in [pair_name(kept[a], kept[b])]
    ]
    for loop in [] if notes else _overwound(kept, parent, screened.areas):
        message = f"loop {loop} winds twice or backwards once its slits are removed"
        notes.append((loop, Diagnostic("LOOPS_CROSS", Severity.ERROR, message, f"loop {loop}")))
        at = screened.slit_loops == loop
        crossings = (
            np.vstack([crossings[0], screened.slit_ends[at]]),
            np.vstack([crossings[1], np.full((int(at.sum()), 2), loop, np.int64)]),
        )
    if notes:
        keyed = [*zip(screened.diagnostic_loops, diagnostics, strict=True), *notes]
        ordered = tuple(d for _, d in sorted(keyed, key=lambda pair: pair[0]))  # stable
        return Result(_empty_tree(*crossings), ordered)
    pieces: list[CurveRows] = []
    for position, piece in enumerate(screened.rows):
        rows = CurveRows(piece.rows, piece.ids, _ONE_LOOP)
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
