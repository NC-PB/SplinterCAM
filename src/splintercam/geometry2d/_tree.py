# SPDX-License-Identifier: Apache-2.0
"""The loop tree: parents by containment probes, depths and normalised orientation (research 01,
Loop tree, rules 5 and 6)."""

import numpy as np

from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._contain import nest
from ._loops import LoopTree
from ._rows import CurveRows
from ._screen import Screened, screen_loops

_ONE_LOOP = np.zeros(1, np.int64)


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
    if any(d.severity is Severity.ERROR for d in diagnostics):  # crossings or refusals, REQ-G2D-162
        return Result(_empty_tree(screened), tuple(diagnostics))
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
                f"loops {kept[a]} and {kept[b]} contain each other, or do not nest",
                f"loops {kept[a]} and {kept[b]}",
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
        for where in [f"loops {kept[a]} and {kept[b]}"]
    ]
    if notes:
        keyed = [*zip(screened.diagnostic_loops, diagnostics, strict=True), *notes]
        ordered = tuple(d for _, d in sorted(keyed, key=lambda pair: pair[0]))  # stable
        return Result(_empty_tree(screened), ordered)
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
