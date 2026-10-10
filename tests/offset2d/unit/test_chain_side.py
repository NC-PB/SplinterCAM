# SPDX-License-Identifier: Apache-2.0
"""Unit tests of `offset_chain_side` (plan 0005, step 8, part 2): research 02's test 12 (a chain of
a line and two arcs on both sides, the sharp V, the C), the omega with a closed piece, IDs, order
and the refusals."""

import dataclasses
import itertools
import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes
from offset2d_oracles import distance_to_curves
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


@pytest.mark.req("REQ-OFF-028")
def test_the_sharp_v_on_its_outside_runs_unbroken_round_the_join(ctx: Context) -> None:
    # Research 02, test 12: (-10, 0) to (0, 0) to (-10, 1), the tool on the outside (the right,
    # the V turns left): one open piece round the tip.
    paths = run(SHARP_V, RIGHT, 1.0, ctx)
    assert paths.closed.tolist() == [False]
    piece = pieces(paths)[0]
    assert piece[:, 0].max() >= 1.0  # round the tip at (0, 0)
    assert np.linalg.norm(piece[0] - np.array([-10.0, -1.0])) < 0.01


@pytest.mark.req("REQ-OFF-028")
def test_a_c_open_narrower_than_2t_with_the_tool_inside_is_one_open_piece(ctx: Context) -> None:
    # Research 02, test 12, the C: an arc of radius 10 open over 20 degrees, t = 6, the tool
    # inside. Its inner wall runs from cap to cap: the edges near the mouth lie nearest the
    # chain's ends, so they are caps by research 02's own rule, and the tool cannot pass the tips
    # anyway. One open piece, no closed one (DEC-OFF-018; research 02 expects a closed piece too).
    h = math.radians(10.0)
    c = [[10 * math.cos(h), 10 * math.sin(h), 10 * math.cos(h), -10 * math.sin(h), 0.0, 0.0,
          2 * math.pi - 2 * h]]  # fmt: skip
    paths = run(c, LEFT, 6.0, ctx)
    assert paths.closed.tolist() == [False]
    radii = np.hypot(paths.points[:, 0], paths.points[:, 1])
    assert radii.max() <= 10.0 - 6.0 + 0.01


@pytest.mark.req("REQ-OFF-028")
def test_a_room_behind_a_neck_narrower_than_2t_is_a_closed_piece(ctx: Context) -> None:
    # The case of a closed piece: an omega, the tool inside a room whose neck (2 mm) is narrower
    # than 2t. The bands of the neck's walls meet, so the room is enclosed by tool-side edges
    # only: one closed piece; the base line's tool side one open piece below it.
    omega = polyline([(-20.0, 0.0), (-1.0, 0.0), (-1.0, 5.0), (-10.0, 5.0), (-10.0, 20.0),
                      (10.0, 20.0), (10.0, 5.0), (1.0, 5.0), (1.0, 0.0), (20.0, 0.0)])  # fmt: skip
    paths = run(omega, RIGHT, 3.0, ctx)
    flags: list[bool] = paths.closed.tolist()
    assert sorted(flags) == [False, True]
    closed = pieces(paths)[flags.index(True)]
    d = distance_to_curves(closed, as_rows(flat_chain(omega, RIGHT, ctx)))
    assert d.min() >= 3.0  # the room's loop in the band: it rounds the neck's corners at t
    assert d.max() <= band_top(3.0, ctx)
    assert closed[:, 1].min() > 5.0  # above the room's floor
    open_piece = pieces(paths)[flags.index(False)]
    d = distance_to_curves(open_piece, as_rows(flat_chain(omega, RIGHT, ctx)))
    assert d.min() >= 3.0  # in the band, rounding the neck's corners at t below its mouth
    assert d.max() <= band_top(3.0, ctx)
    assert open_piece[:, 1].max() < 0.0  # below the base line


@pytest.mark.req("REQ-OFF-011", "REQ-OFF-038")
def test_the_same_input_gives_the_same_arrays(ctx: Context) -> None:
    first, again = run(MIXED, LEFT, 2.0, ctx), run(MIXED, LEFT, 2.0, ctx)
    for field in ("points", "starts", "closed", "source_ids", "fixed"):
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
