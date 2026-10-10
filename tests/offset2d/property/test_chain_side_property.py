# SPDX-License-Identifier: Apache-2.0
"""Property tests of `offset_chain_side` (REQ-OFF-028; plan 0005, backlog of step 8): random open
chains of lines and arcs on the 2^-20 grid, at tol 0.01 mm, tol_min and 0.05 mm (D-146).

A chain is refused when it is not simple, decided here by oracles independent of the kernel's
`find_contact`, on the chain merged as REQ-OFF-028 says: the smallest distance between segments not
next to each other (a contact), and a segment running back over the one before it (a fold). Near
t_topo either answer is right (the kernel merges points within t_topo first), so the oracles demand
a refusal on the sure side of a window round t_topo and an offset on the other. An accepted
chain's pieces lie in the band [t, t + a + 6u] from the flattened chain (t_topo more where a point
merged), no closer than t to the true curves, on the tool's side only, run with the chain, carry
the input's IDs and valid flags, start a closed piece at its smallest point and flag it enclosed
exactly on a hole, and come out bit for bit the same twice (DEC-OFF-024).
"""

import dataclasses
import itertools
import math
import os
import re
from typing import NamedTuple

import numpy as np
import pytest
from hypothesis import HealthCheck, event, example, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from geometry2d_checks import codes
from offset2d_oracles import distance_to_curves, offset_band_mm
from offset2d_strategies import ChainCase, open_chains
from splintercam.foundation import Context, Result, ToleranceSet
from splintercam.geometry2d import AirSide, CurveRows, build_chain
from splintercam.offset2d import EdgeClass, OpenPaths, SourceClasses, offset_chain_side

# As test 10 (test_offset_region_property.py): fewer examples than the profile's, since a chain
# flattened at tol_min holds hundreds of chords per arc.
EXAMPLES = 1000 if os.environ.get("HYPOTHESIS_PROFILE") == "thorough" else 25  # tests/conftest.py
TOLERANCES_MM = [0.01, 0.0022858, 0.05]  # tol, tol_min, roughing (D-146), as test 10
# The distance oracle's error, 64·ε·S (`offset2d_oracles`), below 1e-11 mm for S = 200 mm here;
# 1e-9 mm bounds it with room and stays five orders below u.
ORACLE_SLACK_MM = 1e-9
NAN = math.nan
_BLOCK = 256  # segments per block of the pair distances; bounds memory, not a tolerance
_LOCATION = re.compile(r"\((-?[\d.]+), (-?[\d.]+)\) mm")
_LOCATION_DIGITS_MM = 5e-5  # the diagnostic prints 4 decimals


def _with_tol(ctx: Context, tol_mm: float) -> Context:
    built = ToleranceSet.for_operation(tol_mm)
    assert built.value is not None, built.diagnostics
    return dataclasses.replace(ctx, tolerances=built.value)


def _polyline(points: list[tuple[float, float]], side: AirSide, ending: str = "walk") -> ChainCase:
    return ChainCase([[*p, *q, NAN, NAN, 0.0] for p, q in itertools.pairwise(points)], side, ending)


def _call(
    rows: NDArray[np.float64], ids: NDArray[np.int64], side: AirSide, t_mm: float, ctx: Context
) -> Result[OpenPaths]:
    classes = SourceClasses(ids, np.full(ids.size, int(EdgeClass.MATERIAL), dtype=np.int8))
    return offset_chain_side(rows, ids, side, t_mm, classes, ctx)


def _segment_point(
    q: NDArray[np.float64], a: NDArray[np.float64], b: NDArray[np.float64]
) -> NDArray[np.float64]:
    d = b - a
    dd = np.maximum((d * d).sum(axis=-1), np.finfo(np.float64).tiny)
    s = np.clip(((q - a) * d).sum(axis=-1) / dd, 0.0, 1.0)
    return np.hypot(*np.moveaxis(q - a - s[..., None] * d, -1, 0))


def _orient(
    a: NDArray[np.float64], b: NDArray[np.float64], c: NDArray[np.float64]
) -> NDArray[np.float64]:
    return np.sign((b[..., 0] - a[..., 0]) * (c[..., 1] - a[..., 1])
                   - (b[..., 1] - a[..., 1]) * (c[..., 0] - a[..., 0]))  # fmt: skip


def merged_chain(points: NDArray[np.float64], t_topo: float) -> NDArray[np.float64]:
    """REQ-OFF-028's merge read independently of `keep_chain`: a point within t_topo of the last
    kept one is dropped; the ends stay, so a kept point within t_topo of the end gives way to it."""
    kept = [points[0]]
    for q in points[1:-1]:  # a test oracle over a few hundred points
        if float(np.hypot(*(q - kept[-1]))) > t_topo:
            kept.append(q)
    while len(kept) > 1 and float(np.hypot(*(points[-1] - kept[-1]))) <= t_topo:
        kept.pop()
    return np.array([*kept, points[-1]])


def nearest_non_adjacent(points: NDArray[np.float64]) -> float:
    """The smallest distance between two segments of the polyline that are not next to each other
    (index apart by 2 or more): 0 where they cross, else the least end-to-segment distance."""
    a, b = points[:-1], points[1:]
    m = int(a.shape[0])
    best = np.inf
    for start in range(0, m, _BLOCK):
        stop = min(start + _BLOCK, m)
        j, i = np.arange(m, dtype=np.int64), np.arange(start, stop, dtype=np.int64)
        pair: NDArray[np.bool_] = j[None, :] >= i[:, None] + 2
        if not pair.any():
            continue
        ai, bi = a[start:stop, None, :], b[start:stop, None, :]  # (block, 1, 2)
        aj, bj = a[None, :, :], b[None, :, :]  # (1, m, 2); every pair by broadcasting
        d = np.minimum.reduce([
            _segment_point(ai, aj, bj), _segment_point(bi, aj, bj),
            _segment_point(aj, ai, bi), _segment_point(bj, ai, bi),
        ])  # fmt: skip
        crossing = (_orient(ai, bi, aj) * _orient(ai, bi, bj) < 0) & (
            _orient(aj, bj, ai) * _orient(aj, bj, bi) < 0
        )
        d = np.where(crossing, 0.0, d)
        best = min(best, float(d[pair].min()))
    return best


class _Folds(NamedTuple):
    sure: NDArray[np.bool_]  # per vertex: the segment after it surely runs back over the one before
    possible: NDArray[np.bool_]  # within the window round t_topo


def folds(chain: NDArray[np.float64], t_topo: float) -> _Folds:
    """The SPEC's fold (Failure modes), read per interior vertex of the merged chain: the segment
    after it runs opposite to the one before, its end within t_topo of that one's line, overlapping
    it by more than t_topo; sure with t_topo/2 and 2·t_topo, possible with 2·t_topo and t_topo/2."""
    first, second = chain[1:-1] - chain[:-2], chain[2:] - chain[1:-1]
    length = np.hypot(first[:, 0], first[:, 1])
    dot = (first * second).sum(axis=1)
    off_line = np.abs(first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0]) / length
    overlap = np.minimum(-dot / length, length)
    back = dot < 0.0
    sure = back & (off_line <= t_topo / 2.0) & (overlap >= 2.0 * t_topo)
    possible = back & (off_line <= 2.0 * t_topo) & (overlap > t_topo / 2.0)
    return _Folds(sure, possible)


def _pieces(paths: OpenPaths) -> list[NDArray[np.float64]]:
    ends = [*paths.starts.tolist()[1:], paths.points.shape[0]]
    return [paths.points[a:b] for a, b in zip(paths.starts.tolist(), ends, strict=True)]


def _edges(paths: OpenPaths) -> tuple[NDArray[np.float64], NDArray[np.float64], list[int]]:
    """Every edge of every piece as its start and end, a closed piece's closing edge included, and
    the number of edges per piece."""
    starts: list[NDArray[np.float64]] = []
    ends: list[NDArray[np.float64]] = []
    for piece, closed in zip(_pieces(paths), paths.closed.tolist(), strict=True):
        ends.append(np.roll(piece, -1, axis=0) if closed else piece[1:])
        starts.append(piece if closed else piece[:-1])
    return np.concatenate(starts), np.concatenate(ends), [e.shape[0] for e in ends]


def _nearest_segment(q: NDArray[np.float64], chain: NDArray[np.float64]) -> NDArray[np.int64]:
    a, b = chain[:-1][None], chain[1:][None]
    return np.argmin(_segment_point(q[:, None, :], a, b), axis=1)


def _as_rows(points: NDArray[np.float64]) -> CurveRows:
    lines = np.full((points.shape[0] - 1, 3), [np.nan, np.nan, 0.0])  # cx, cy, sweep of a line
    rows = np.column_stack([points[:-1], points[1:], lines])
    return CurveRows(rows, np.arange(rows.shape[0], dtype=np.int64), np.array([0]))


def _check_refusal(
    result: Result[OpenPaths], chain: NDArray[np.float64], gap: float, t_topo: float
) -> None:
    """A refusal names a closed chain only where its ends meet (REQ-OFF-029), a contact only where
    the contact oracle finds parts within 2·t_topo, and a fold only where the fold oracle allows
    one, at its place: on the segment after that vertex."""
    found = codes(result)
    assert len(found) == 1
    if found[0] == "CHAIN_CLOSED":  # a contact line that runs back onto the chain's start
        assert np.array_equal(chain[0], chain[-1])
        return
    if found[0] == "CHAIN_SELF_CONTACT":
        assert gap <= 2.0 * t_topo
        return
    assert found[0] == "CHAIN_FOLDS"
    possible = np.flatnonzero(folds(chain, t_topo).possible)
    assert possible.size > 0
    match = _LOCATION.fullmatch(result.diagnostics[-1].location or "")
    assert match is not None
    at = np.array([[float(match[1]), float(match[2])]])
    on = _segment_point(at, chain[possible + 1], chain[possible + 2])  # the segments that fold
    assert float(on.min()) <= 2.0 * _LOCATION_DIGITS_MM


class _Side(NamedTuple):
    either: NDArray[np.bool_]  # on the tool's side of the nearest segment, or of either at a vertex
    both: NDArray[np.bool_]  # of the nearest segment, and of both at a vertex
    at_end: NDArray[np.bool_]  # the nearest point is an end of the chain (a cap)


def _side(q: NDArray[np.float64], chain: NDArray[np.float64], sign: float) -> _Side:
    """REQ-OFF-028's side rule, read independently: by orient2d against the nearest segment inside
    it; at an interior vertex the requirement takes either segment where the vertex is convex toward
    the tool and both where it is concave, which this reads as the bounds "either" and "both"."""
    a, b = chain[:-1], chain[1:]
    k = _nearest_segment(q, chain)
    d = b - a
    cross = d[None, :, 0] * (q[:, None, 1] - a[None, :, 1]) - d[None, :, 1] * (
        q[:, None, 0] - a[None, :, 0]
    )
    side = cross * sign > 0.0  # (n, segments)
    rows = np.arange(int(q.shape[0]), dtype=np.int64)
    s = ((q - a[k]) * d[k]).sum(axis=1) / (d[k] * d[k]).sum(axis=1)
    last = d.shape[0] - 1
    before = np.where((s <= 0.0) & (k > 0), k - 1, k)  # the segment before a vertex at the start
    after = np.where((s >= 1.0) & (k < last), k + 1, k)  # the one after, at the end
    own, early, late = side[rows, k], side[rows, before], side[rows, after]
    at_end = ((s <= 0.0) & (k == 0)) | ((s >= 1.0) & (k == last))
    return _Side(own | early | late, own & early & late, at_end)


def _check_no_room(case: ChainCase, chain: NDArray[np.float64], t_mm: float, ctx: Context) -> None:
    """An empty side means the tool fits nowhere: no point t + 2·band beside the middle of a
    segment of the merged chain lies t + band or more from it with its nearest point inside the
    chain (not a cap) and on the tool's side by both readings; there the grown area would have a
    tool-side boundary between it and the chain."""
    band = offset_band_mm(ctx.tolerances)
    d = np.diff(chain, axis=0)
    normal = np.column_stack([-d[:, 1], d[:, 0]]) / np.hypot(d[:, 0], d[:, 1])[:, None]  # left
    sign = 1.0 if case.side is AirSide.LEFT else -1.0
    probe = (chain[:-1] + chain[1:]) / 2.0 + sign * (t_mm + 2.0 * band) * normal
    side = _side(probe, chain, sign)
    clear = distance_to_curves(probe, _as_rows(chain)) >= t_mm + band
    assert not (clear & side.both & ~side.at_end).any()


def _check_paths(  # noqa: PLR0913 (the example's parts, each checked here)
    case: ChainCase,
    paths: OpenPaths,
    flat: NDArray[np.float64],
    chain: NDArray[np.float64],
    t_mm: float,
    ctx: Context,
) -> None:
    tol = ctx.tolerances
    open_count = int(np.count_nonzero(~paths.closed))
    assert paths.closed.size >= 1
    assert paths.closed.tolist() == sorted(paths.closed.tolist())  # open pieces first
    # The first open piece is reachable (DEC-OFF-019); with none, caps closer than 2t shut the
    # tool's side into a room, a closed piece on a hole.
    assert open_count == 0 or not bool(paths.enclosed[0])
    assert paths.fixed.shape == (paths.points.shape[0],)
    assert set(np.unique(paths.fixed).tolist()) <= {0, 1}
    assert paths.source_ids.size == paths.points.shape[0] - open_count
    assert set(paths.source_ids.tolist()) <= set(range(100, 100 + len(case.rows)))
    pieces = zip(_pieces(paths), paths.closed.tolist(), paths.enclosed.tolist(), strict=True)
    for piece, closed, enclosed in pieces:
        if not closed:
            continue
        # REQ-OFF-038: a closed piece starts at its smallest point, by x, then y.
        assert int(np.lexsort((piece[:, 1], piece[:, 0]))[0]) == 0
        # DEC-OFF-019, 020: a closed piece is enclosed exactly when it lies on a hole of the grown
        # area. Holes run clockwise, outer loops counter-clockwise, and with the tool left every
        # piece is turned round, so a hole's piece runs counter-clockwise for the tool left.
        x, y = piece[:, 0], piece[:, 1]
        area = float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))
        assert enclosed == ((area > 0.0) == (case.side is AirSide.LEFT))
    start, end, counts = _edges(paths)
    middles = (start + end) / 2.0
    probes = np.concatenate([paths.points, middles])
    merged = chain.shape[0] < flat.shape[0]
    top = t_mm + offset_band_mm(tol) + (tol.topology_tol_mm if merged else 0.0)
    d = distance_to_curves(probes, _as_rows(flat))
    assert d.min() >= t_mm - ORACLE_SLACK_MM
    assert d.max() <= top + ORACLE_SLACK_MM
    rows = np.array(case.rows, dtype=np.float64)
    true = CurveRows(rows, np.arange(rows.shape[0], dtype=np.int64), np.array([0]))
    assert distance_to_curves(probes, true).min() >= t_mm - ORACLE_SLACK_MM
    # Every edge middle on the tool's side of the merged chain, which the labels see (REQ-OFF-028
    # labels edges by their middles; a piece's last vertex may lie on a cap).
    assert _side(middles, chain, 1.0 if case.side is AirSide.LEFT else -1.0).either.all()
    # Every piece runs with the chain (DEC-OFF-020): its edges, weighted by length, go the way of
    # the chain segments nearest their middles.
    k = _nearest_segment(middles, chain)
    along = ((end - start) * (chain[k + 1] - chain[k])).sum(axis=1)
    for a, b in itertools.pairwise(np.cumsum([0, *counts]).tolist()):
        assert along[a:b].sum() > 0.0


@pytest.mark.req("REQ-OFF-028", "REQ-OFF-038")
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=EXAMPLES,
)
@given(case=open_chains(), t_mm=st.floats(0.1, 10.0), tol_mm=st.sampled_from(TOLERANCES_MM))
# The chains earlier runs found where the test's reading was wrong (DEC-OFF-024), kept as examples.
@example(
    _polyline(
        [
            (0, 0),
            (1, 0),
            (1.5403022766113281, 0.8414707183837891),
            (2.0806045532226562, 1.6829414367675781),
            (1.6644573211669922, 2.592238426208496),
            (0.6744651794433594, 2.733358383178711),
            (0.020821571350097656, 1.9765558242797852),
            (0.30448341369628906, 1.0176315307617188),
        ],
        AirSide.RIGHT,
    ),
    1.0,
    0.01,
)  # a piece's last vertex on a cap
@example(
    ChainCase(
        [
            [0.0, 0.0, 1.0, 0.0, 0.5, -0.5729166666666666, -1.435082681082289],
            [1.0, 0.0, 1.5403022766113281, 0.8414707183837891, NAN, NAN, 0.0],
        ],
        AirSide.RIGHT,
        "walk",
    ),
    1.0,
    0.01,
)  # nearest an interior vertex
@example(
    ChainCase(
        [
            [0.0, 0.0, 1.0, 0.0, NAN, NAN, 0.0],
            [1.0, 0.0, 3.0, 0.0, 2.0, -1.0846875, -1.4895937867070168],
            [3.0, 0.0, 3.000033378601074, 5.14984130859375e-05, NAN, NAN, 0.0],
        ],
        AirSide.LEFT,
        "walk",
    ),
    1.0,
    0.0022858,
)  # a stub at the end, merged
@example(
    ChainCase(
        [
            [0.0, 0.0, 9.5367431640625e-06, 0.0, NAN, NAN, 0.0],
            [
                9.5367431640625e-06,
                0.0,
                1.0,
                0.0,
                0.500004768371582,
                0.9374910593032837,
                0.9799146525074566,
            ],
        ],
        AirSide.LEFT,
        "walk",
    ),
    2.0,
    0.01,
)  # empty: radius < t
@example(
    _polyline([(0, 0), (1, 0), (1.000009536743164, 0), (0.5, 0)], AirSide.LEFT, "contact"),
    1.0,
    0.01,
)  # a contact line over a merged stub: a fold
@example(
    _polyline(
        [
            (0, 0),
            (0.5403022766113281, 0.8414707183837891),
            (0.5403499603271484, 0.8415441513061523),
            (0, 0),
        ],
        AirSide.LEFT,
        "contact",
    ),
    1.0,
    0.01,
)  # a contact line onto the start: closed
@example(
    _polyline(
        [
            (0, 0),
            (1, 0),
            (4, 0),
            (4.540302276611328, 0.8414707183837891),
            (8.322418212890625, 6.731767654418945),
            (5.4413042068481445, 9.506507873535156),
            (0.49134159088134766, 10.21210765838623),
            (-0.4451150894165039, 9.861324310302734),
            (-1.3815717697143555, 9.510540962219238),
        ],
        AirSide.LEFT,
    ),
    5.0,
    0.01,
)  # a room away from the ends, cut off by the caps: one closed piece
def test_a_simple_chain_is_offset_on_its_tool_side_and_others_are_refused(
    ctx: Context, case: ChainCase, t_mm: float, tol_mm: float
) -> None:
    ctx = _with_tol(ctx, tol_mm)
    rows = np.array(case.rows, dtype=np.float64)
    ids = 100 + np.arange(rows.shape[0], dtype=np.int64)
    built = build_chain(rows, ids, case.side, ctx).value
    assert built is not None
    flat = built.points
    t_topo = ctx.tolerances.topology_tol_mm
    chain = merged_chain(flat, t_topo)
    gap = nearest_non_adjacent(chain)
    result = _call(rows, ids, case.side, t_mm, ctx)
    event("ending", case.ending)
    event("outcome", codes(result)[-1] if codes(result) else "offset")
    event("merged", str(chain.shape[0] < flat.shape[0]))
    if result.value is None:
        _check_refusal(result, chain, gap, t_topo)
        return
    assert not folds(chain, t_topo).sure.any()  # a chain that folds is never offset
    assert gap >= t_topo / 2.0  # nor one that touches or crosses itself
    if codes(result) == ["OFFSET_EMPTY"]:  # the chain curls tighter than t round the tool
        assert result.value.points.shape[0] == 0
        _check_no_room(case, chain, t_mm, ctx)
        return
    assert codes(result) == []
    _check_paths(case, result.value, flat, chain, t_mm, ctx)
    again = _call(rows, ids, case.side, t_mm, ctx).value  # REQ-OFF-038: bit for bit the same
    assert again is not None
    for field in ("points", "starts", "closed", "enclosed", "source_ids", "fixed"):
        assert np.array_equal(getattr(again, field), getattr(result.value, field)), field
