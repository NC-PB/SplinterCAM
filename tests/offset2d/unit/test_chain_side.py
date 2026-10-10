# SPDX-License-Identifier: Apache-2.0
"""Unit tests of `offset_chain_side` (plan 0005, step 8, part 2): research 02's test 12 (a chain of
a line and two arcs on both sides, the sharp V, the C), the omega with a closed piece, IDs, order
and the refusals."""

import dataclasses
import itertools
import math
from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes
from offset2d_oracles import distance_to_curves
from splintercam import _kernels
from splintercam.foundation import CANCELLED, TOLERANCE_DEFAULTS, CancellationToken, Context
from splintercam.geometry2d import AirSide, CurveRows, build_chain
from splintercam.offset2d import EdgeClass, OpenPaths, SourceClasses, offset_chain_side

NAN = math.nan
LEFT, RIGHT = AirSide.LEFT, AirSide.RIGHT
# Research 02, test 12: a line, a counter-clockwise arc and a clockwise arc.
MIXED = [
    [0.0, 0.0, 20.0, 0.0, NAN, NAN, 0.0],
    [20.0, 0.0, 30.0, 10.0, 20.0, 10.0, math.pi / 2],
    [30.0, 10.0, 40.0, 20.0, 40.0, 10.0, -math.pi / 2],
]
SHARP_V = [[-10.0, 0.0, 0.0, 0.0, NAN, NAN, 0.0], [0.0, 0.0, -10.0, 1.0, NAN, NAN, 0.0]]


def polyline(points: list[tuple[float, float]]) -> list[list[float]]:
    return [[*p, *q, NAN, NAN, 0.0] for p, q in itertools.pairwise(points)]


def run(rows: list[list[float]], side: AirSide, t_mm: float, ctx: Context) -> OpenPaths:
    r, ids = np.array(rows, dtype=np.float64), 100 + np.arange(len(rows), dtype=np.int64)
    classes = SourceClasses(ids, np.full(ids.size, int(EdgeClass.MATERIAL), dtype=np.int8))
    result = offset_chain_side(r, ids, side, t_mm, classes, ctx)
    assert result.value is not None, result.diagnostics
    return result.value


def pieces(paths: OpenPaths) -> list[NDArray[np.float64]]:
    ends = [*paths.starts.tolist()[1:], paths.points.shape[0]]
    return [paths.points[a:b] for a, b in zip(paths.starts.tolist(), ends, strict=True)]


def flat_chain(rows: list[list[float]], side: AirSide, ctx: Context) -> NDArray[np.float64]:
    r, ids = np.array(rows, dtype=np.float64), 100 + np.arange(len(rows), dtype=np.int64)
    built = build_chain(r, ids, side, ctx).value
    assert built is not None
    return built.points


def as_rows(points: NDArray[np.float64]) -> CurveRows:
    lines = np.full((points.shape[0] - 1, 3), [NAN, NAN, 0.0])  # cx, cy, sweep of a line
    rows = np.column_stack([points[:-1], points[1:], lines])
    return CurveRows(rows, np.arange(rows.shape[0], dtype=np.int64), np.array([0]))


def signed_side(q: NDArray[np.float64], chain: NDArray[np.float64]) -> NDArray[np.float64]:
    """Per point, the side of the nearest chain segment it lies on: > 0 left, < 0 right."""
    a, b = chain[:-1], chain[1:]
    d = b - a
    t = np.clip(((q[:, None, :] - a[None]) * d[None]).sum(axis=2) / (d * d).sum(axis=1), 0.0, 1.0)
    nearest = a[None] + t[:, :, None] * d[None]
    k = np.argmin(((q[:, None, :] - nearest) ** 2).sum(axis=2), axis=1)
    rel = q - a[k]
    return d[k, 0] * rel[:, 1] - d[k, 1] * rel[:, 0]


def band_top(t_mm: float, ctx: Context) -> float:
    margin = TOLERANCE_DEFAULTS["rounding_margin_grid_units"].default
    return t_mm + ctx.tolerances.arc_tol_mm + margin * ctx.tolerances.grid_unit_mm


@pytest.mark.req("REQ-OFF-028")
@pytest.mark.parametrize("side", [LEFT, RIGHT])
def test_a_line_and_two_arcs_on_either_side(side: AirSide, ctx: Context) -> None:
    # Research 02, test 12: one open piece, cap to cap in the chain's direction, every vertex in
    # [t, t + a + 6u] of the chain flattened with the tool's side as the arcs' air side, and on the
    # tool's side only.
    t_mm = 2.0
    paths = run(MIXED, side, t_mm, ctx)
    assert paths.closed.tolist() == [False]
    chain = flat_chain(MIXED, side, ctx)
    piece = pieces(paths)[0]
    d = distance_to_curves(piece, as_rows(chain))
    assert d.min() >= t_mm
    assert d.max() <= band_top(t_mm, ctx)
    sign = 1.0 if side is LEFT else -1.0
    assert (signed_side(piece, chain) * sign > 0.0).all()
    normal = np.array([0.0, 1.0]) * sign  # at the start the chain runs along +x
    assert np.linalg.norm(piece[0] - (chain[0] + t_mm * normal)) <= band_top(t_mm, ctx) - t_mm
    assert np.linalg.norm(piece[-1] - chain[-1]) == pytest.approx(
        t_mm, abs=band_top(t_mm, ctx) - t_mm
    )
    assert paths.source_ids.size == piece.shape[0] - 1
    assert set(paths.source_ids.tolist()) == {100, 101, 102}
    true = CurveRows(np.array(MIXED), 100 + np.arange(3, dtype=np.int64), np.array([0]))
    assert distance_to_curves(piece, true).min() >= t_mm  # no closer than t to the true arcs


@pytest.mark.req("REQ-OFF-028")
def test_the_sharp_v_on_its_outside_runs_unbroken_round_the_join(ctx: Context) -> None:
    # Research 02, test 12: (-10, 0) to (0, 0) to (-10, 1), the tool on the outside (the right,
    # the V turns left): one open piece round the tip.
    paths = run(SHARP_V, RIGHT, 1.0, ctx)
    assert paths.closed.tolist() == [False]
    piece = pieces(paths)[0]
    assert piece[:, 0].max() >= 1.0  # round the tip at (0, 0)
    slack = band_top(1.0, ctx) - 1.0
    assert np.linalg.norm(piece[0] - np.array([-10.0, -1.0])) <= slack
    normal = np.array([1.0, 10.0]) / math.hypot(1.0, 10.0)  # right of the second segment
    assert np.linalg.norm(piece[-1] - (np.array([-10.0, 1.0]) + normal)) <= slack
    d = distance_to_curves(piece, as_rows(flat_chain(SHARP_V, RIGHT, ctx)))
    assert d.min() >= 1.0
    assert d.max() <= band_top(1.0, ctx)


@pytest.mark.req("REQ-OFF-028")
def test_a_c_open_narrower_than_2t_with_the_tool_inside_is_one_open_piece(ctx: Context) -> None:
    # Research 02, test 12, the C: an arc of radius 10 open over 20 degrees, t = 6, the tool
    # inside. The round ends close the mouth, but the edges there lie nearest the chain's ends,
    # so they are caps by research 02's own rule: the inner wall is one open piece from cap to
    # cap, no closed one (DEC-OFF-018; research 02 expects a closed piece).
    h = math.radians(10.0)
    c = [[10 * math.cos(h), 10 * math.sin(h), 10 * math.cos(h), -10 * math.sin(h), 0.0, 0.0,
          2 * math.pi - 2 * h]]  # fmt: skip
    paths = run(c, LEFT, 6.0, ctx)
    assert paths.closed.tolist() == [False]
    radii = np.hypot(paths.points[:, 0], paths.points[:, 1])
    assert radii.max() <= 10.0 - 6.0 + band_top(6.0, ctx) - 6.0
    tol = ctx.tolerances  # it hugs the inner wall: within the band of the inscribed chords
    assert radii.min() >= 10.0 - band_top(6.0, ctx) - tol.flatten_tol_mm


OMEGA = [(-20.0, 0.0), (-1.0, 0.0), (-1.0, 5.0), (-10.0, 5.0), (-10.0, 20.0), (10.0, 20.0),
         (10.0, 5.0), (1.0, 5.0), (1.0, 0.0), (20.0, 0.0)]  # fmt: skip


def signed_area(loop: NDArray[np.float64]) -> float:
    x, y = loop[:, 0], loop[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


@pytest.mark.req("REQ-OFF-028", "REQ-OFF-038")
@pytest.mark.parametrize("side", [LEFT, RIGHT])
def test_a_room_behind_a_neck_narrower_than_2t_is_an_enclosed_closed_piece(
    side: AirSide, ctx: Context
) -> None:
    # The case of a closed piece: an omega, the tool inside a room whose neck (2 mm) is narrower
    # than 2t (the chain run backwards for the tool on the left). The bands of the neck's walls
    # meet, so the room is enclosed by tool-side edges only: one closed piece, enclosed, after the
    # open piece below the base line (DEC-OFF-019). It runs with the chain like the open piece, so
    # the walls lie on the side away from the tool: clockwise round the room for the tool on the
    # right, counter-clockwise on the left (DEC-OFF-020); from its smallest point (REQ-OFF-038).
    omega = polyline(OMEGA if side is RIGHT else OMEGA[::-1])
    paths = run(omega, side, 3.0, ctx)
    assert paths.closed.tolist() == [False, True]  # open pieces first
    assert paths.enclosed.tolist() == [False, True]
    open_piece, closed = pieces(paths)
    chain = as_rows(flat_chain(omega, side, ctx))
    for piece in (open_piece, closed):
        d = distance_to_curves(piece, chain)
        assert d.min() >= 3.0  # in the band, rounding the neck's corners at t
        assert d.max() <= band_top(3.0, ctx)
    assert closed[:, 1].min() > 5.0  # above the room's floor
    assert open_piece[:, 1].max() < 0.0  # below the base line
    assert signed_area(closed) * (1.0 if side is LEFT else -1.0) > 0.0
    assert open_piece[0, 0] * (1.0 if side is RIGHT else -1.0) < 0.0  # from the chain's start
    corners: list[tuple[float, float]] = [(float(x), float(y)) for x, y in closed.tolist()]
    assert corners[0] == min(corners)
    walls = set(paths.source_ids[open_piece.shape[0] - 1 :].tolist())
    assert {103, 104, 105} <= walls <= set(range(101, 108))  # the room's walls, either way round


@pytest.mark.req("REQ-OFF-028")
def test_a_chain_crossing_itself_gives_open_pieces_along_the_chain(ctx: Context) -> None:
    # (0, 0) to (20, 0) to (20, 10) to (10, 10) to (10, -10), the tool left, t = 1: the last
    # segment crosses the first, so the tool side breaks into an open piece above the first
    # segment's start, an open piece right of the last segment's end, and the hook's room. The
    # open pieces come in the chain's order and both run with it; both are on the outer loop,
    # reachable; the room is enclosed.
    paths = run(polyline([(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (10.0, 10.0), (10.0, -10.0)]),
                LEFT, 1.0, ctx)  # fmt: skip
    assert paths.closed.tolist() == [False, False, True]
    assert paths.enclosed.tolist() == [False, False, True]
    first, second, _ = pieces(paths)
    slack = band_top(1.0, ctx) - 1.0
    assert np.abs(first[[0, -1]] - [[0.0, 1.0], [9.0, 1.0]]).max() <= slack
    assert np.abs(second[[0, -1]] - [[11.0, -1.0], [11.0, -10.0]]).max() <= slack
    assert set(paths.fixed.tolist()) <= {0, 1}
    for array in (paths.points, paths.starts, paths.closed, paths.enclosed, paths.source_ids):
        assert not array.flags.writeable


@pytest.mark.req("REQ-OFF-028")
def test_a_short_segment_into_an_inside_corner_keeps_t_from_the_chain_start(ctx: Context) -> None:
    # Spec review: (0, 0) to (1, 0) to (1, 10), the tool left, t = 3. The wall along the second
    # segment must not come closer than t to the chain's start: the round end's area keeps it
    # away, and the edges nearest the start are a cap, left out.
    rows = polyline([(0.0, 0.0), (1.0, 0.0), (1.0, 10.0)])
    paths = run(rows, LEFT, 3.0, ctx)
    assert paths.closed.tolist() == [False]
    d = distance_to_curves(paths.points, as_rows(flat_chain(rows, LEFT, ctx)))
    assert d.min() >= 3.0
    assert d.max() <= band_top(3.0, ctx)


@pytest.mark.req("REQ-OFF-028")
@pytest.mark.parametrize("side", [LEFT, RIGHT])
def test_one_line_is_one_edge_run_in_the_chain_direction(side: AirSide, ctx: Context) -> None:
    # A line from (10, 0) to (0, 0), running towards -x: the side is one edge of the grown area,
    # turned to run with the chain whichever way its loop runs.
    paths = run(polyline([(10.0, 0.0), (0.0, 0.0)]), side, 2.0, ctx)
    assert paths.closed.tolist() == [False]
    y = -2.0 if side is LEFT else 2.0
    assert np.allclose(paths.points, [[10.0, y], [0.0, y]], atol=band_top(2.0, ctx) - 2.0)
    assert paths.source_ids.tolist() == [100]


@pytest.mark.req("REQ-OFF-028")
def test_an_inside_corner_on_the_left_rounds_nothing(ctx: Context) -> None:
    # (0, 0) to (10, 0) to (10, 10), the tool left: concave toward the tool, so the piece meets
    # the corner's bisector once, at (10 - t, t), with no arc round it.
    rows = polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])
    piece = pieces(run(rows, LEFT, 2.0, ctx))[0]
    slack = band_top(2.0, ctx) - 2.0
    assert np.linalg.norm(piece[0] - [0.0, 2.0]) <= slack
    assert np.linalg.norm(piece[-1] - [8.0, 10.0]) <= slack
    assert piece.shape[0] == 3
    assert np.linalg.norm(piece[1] - [8.0, 2.0]) <= 2 * slack


FOLDS = {
    "out and back": [(0.0, 0.0), (10.0, 0.0), (0.0, 0.0)],
    "back part way": [(0.0, 0.0), (10.0, 0.0), (2.0, 0.0)],
    "round past the start": [(5.0, 0.0), (10.0, 0.0), (0.0, 0.0), (5.0, 0.0)],
    "a stub of 5u at the start": [(0.0, 0.0), (-5e-4, 0.0), (10.0, 0.0)],
    "a spike": [(0.0, 0.0), (5.0, 0.0), (5.0, -0.01), (5.0, 0.0), (10.0, 0.0)],
    "back 1e-9 above": [(0.0, 0.0), (10.0, 0.0), (10.0, 1e-9), (2.0, 1e-9)],
    "back over itself": [(0.0, 0.0), (10.0, 0.0), (10.0, 5.0), (5.0, 5.0), (5.0, 0.0), (2.0, 0.0)],
}


@pytest.mark.req("REQ-OFF-028")
@pytest.mark.parametrize("name", list(FOLDS))
@pytest.mark.parametrize("side", [LEFT, RIGHT])
def test_a_chain_running_back_over_itself_has_no_side(
    name: str, side: AirSide, ctx: Context
) -> None:
    # Spec reviews: where the chain runs back over itself, one segment calls a place the tool's
    # side and another the material's, so there is no side to cut: refused with CHAIN_FOLDS at
    # the fold (DEC-OFF-018, provisional). Found at a vertex that turns back exactly, or, for the
    # last two, where tied segments disagree (the 1e-9 step merges away first).
    r, ids = np.array(polyline(FOLDS[name])), 100 + np.arange(len(FOLDS[name]) - 1, dtype=np.int64)
    classes = SourceClasses(ids, np.zeros(ids.size, dtype=np.int8))
    result = offset_chain_side(r, ids, side, 2.0, classes, ctx)
    assert result.value is None
    assert codes(result) == ["CHAIN_FOLDS"]
    assert result.diagnostics[-1].location is not None


@pytest.mark.req("REQ-OFF-028")
@pytest.mark.parametrize(
    "stub",
    [
        [(0.0, 0.0), (-5e-5, 0.0), (10.0, 0.0)],
        [(0.0, 0.0), (10.0, 0.0), (10.0 - 5e-5, 0.0)],
        [(0.0, 0.0), (-3.5e-5, 3.5e-5), (10.0, 3.5e-5)],
    ],
    ids=["back at the start", "back at the end", "slanted at the start"],
)
def test_a_stub_shorter_than_the_grid_unit_merges_away(
    stub: list[tuple[float, float]], ctx: Context
) -> None:
    # Spec review, blocker: a stub of 0.5u, which the grid cannot show, turned the round end into
    # tool side and wrapped the path round the start onto the material side. Merged within u, the
    # chain gives the side of the plain line, on its tool side only.
    paths = run(polyline(stub), LEFT, 2.0, ctx)
    plain = run(polyline([(0.0, 0.0), (10.0, 0.0)]), LEFT, 2.0, ctx)
    assert paths.closed.tolist() == [False]
    assert np.abs(paths.points - plain.points).max() <= band_top(2.0, ctx) - 2.0
    assert (paths.points[:, 1] > 2.0).all()


@pytest.mark.req("REQ-OFF-028")
@pytest.mark.parametrize("where", ["start", "corner", "end"])
def test_a_segment_of_eps_len_or_less_merges_into_its_neighbour(where: str, ctx: Context) -> None:
    # A segment half eps_len long at the start, at the corner or at the end gives the side of the
    # chain without it: the side rule needs two real segments at a vertex (DEC-OFF-018).
    e = 0.5 * ctx.tolerances.length_eps_mm
    with_short = {
        "start": [(0.0, 0.0), (e, 0.0), (10.0, 0.0), (10.0, 10.0)],
        "corner": [(0.0, 0.0), (10.0, 0.0), (10.0, e), (10.0, 10.0)],
        "end": [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (10.0, 10.0 + e)],
    }[where]
    plain = run(polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]), LEFT, 2.0, ctx)
    paths = run(polyline(with_short), LEFT, 2.0, ctx)
    assert paths.closed.tolist() == plain.closed.tolist()
    assert paths.points.shape == plain.points.shape
    assert np.abs(paths.points - plain.points).max() <= band_top(2.0, ctx) - 2.0
    # The merged segment takes its longest part's ID: the rows are 100, 101, 102 in order.
    assert set(paths.source_ids.tolist()) == {"start": {101, 102}, "corner": {100, 102},
                                              "end": {100, 101}}[where]  # fmt: skip


@pytest.mark.req("REQ-OFF-011")
def test_the_same_input_gives_the_same_arrays(ctx: Context) -> None:
    first, again = run(MIXED, LEFT, 2.0, ctx), run(MIXED, LEFT, 2.0, ctx)
    for field in ("points", "starts", "closed", "enclosed", "source_ids", "fixed"):
        assert getattr(first, field).tobytes() == getattr(again, field).tobytes()


@pytest.mark.req("REQ-OFF-029", "REQ-OFF-039")
def test_a_closed_chain_is_refused_and_a_point_has_no_side(ctx: Context) -> None:
    square = polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.0, 0.0)])
    r, ids = np.array(square), 100 + np.arange(4, dtype=np.int64)
    classes = SourceClasses(ids, np.zeros(4, dtype=np.int8))
    assert codes(offset_chain_side(r, ids, LEFT, 1.0, classes, ctx)) == ["CHAIN_CLOSED"]
    point = np.array([[5.0, 5.0, 5.0, 5.0, NAN, NAN, 0.0]])
    one = SourceClasses(np.array([100]), np.zeros(1, dtype=np.int8))
    empty = offset_chain_side(point, np.array([100]), LEFT, 1.0, one, ctx)
    assert empty.value is not None
    assert empty.value.starts.size == 0
    assert codes(empty) == ["OFFSET_EMPTY"]


@pytest.mark.req("REQ-OFF-013", "REQ-OFF-041")
def test_bad_arguments_and_cancellation(ctx: Context) -> None:
    r, ids = np.array(MIXED), 100 + np.arange(3, dtype=np.int64)
    classes = SourceClasses(ids, np.zeros(3, dtype=np.int8))
    for t_mm in (0.0, -1.0, math.nan):
        with pytest.raises(ValueError, match="clearance"):
            offset_chain_side(r, ids, LEFT, t_mm, classes, ctx)
    with pytest.raises(ValueError, match="AirSide"):
        offset_chain_side(r, ids, "LEFT", 1.0, classes, ctx)  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="class"):
        offset_chain_side(r, ids, LEFT, 1.0, SourceClasses(ids[:1], np.zeros(1, np.int8)), ctx)
    cancel = CancellationToken()
    cancel.cancel()
    cancelled = dataclasses.replace(ctx, cancel=cancel)
    assert offset_chain_side(r, ids, LEFT, 1.0, classes, cancelled).diagnostics == (CANCELLED,)


@pytest.mark.req("REQ-OFF-018")
def test_a_chain_spanning_the_limit_is_refused(ctx: Context) -> None:
    # 2^26 grid units of 0.0001 mm are 6710.9 mm: a line of 6712 mm is refused.
    r, ids = np.array(polyline([(0.0, 0.0), (6712.0, 0.0)])), np.array([100])
    one = SourceClasses(ids, np.zeros(1, dtype=np.int8))
    assert codes(offset_chain_side(r, ids, LEFT, 1.0, one, ctx)) == ["REGION_TOO_LARGE"]


@pytest.mark.req("REQ-OFF-028")
def test_a_run_of_tiny_steps_merges_without_moving_the_corner(ctx: Context) -> None:
    # Spec review: steps of 0.9 eps_len into a corner merged onto the run's first point moved the
    # corner; 2000 of them, run towards -x, move it 1.8e-3 mm toward the path along the next
    # segment, more than a + 3u. Points within u of the last kept one merge, so the corner moves
    # less than u, and the path keeps t from the chain as given.
    steps = [(-0.9e-6 * i, 0.0) for i in range(2001)]
    points = [(10.0, 0.0), *steps, (steps[-1][0], 10.0)]
    rows = polyline(points)
    paths = run(rows, LEFT, 2.0, ctx)
    d = distance_to_curves(paths.points, as_rows(flat_chain(rows, LEFT, ctx)))
    assert d.min() >= 2.0


@pytest.mark.req("REQ-OFF-028")
def test_more_pieces_than_the_first_room_are_written_on_a_second_call(
    ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A zigzag of sharp tips: the round joins need more vertices than the first allocation, so
    # the kernel runs again with more room, and the pieces and their flags come from that run.
    zigzag = polyline([(0.0, 0.0)] + [(50.0 * (i % 2 == 0), 10.0 * (i + 1)) for i in range(16)])
    rooms: list[int] = []
    kernel = _kernels.offset2d.chain_side

    def spy(*args: Any) -> tuple[int, int, int, list[float] | None]:
        rooms.append(int(args[8].shape[0]))  # points_out
        return kernel(*args)

    monkeypatch.setattr(_kernels.offset2d, "chain_side", spy)
    paths = run(zigzag, LEFT, 2.0, ctx)
    assert len(rooms) == 2
    assert rooms[0] < paths.points.shape[0] <= rooms[1]
    assert paths.closed.tolist() == [False]
    assert paths.enclosed.tolist() == [False]
    d = distance_to_curves(paths.points, as_rows(flat_chain(zigzag, LEFT, ctx)))
    assert d.min() >= 2.0
    assert d.max() <= band_top(2.0, ctx)
