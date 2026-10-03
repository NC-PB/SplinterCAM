# SPDX-License-Identifier: Apache-2.0
"""Unit tests for point in region with the tolerance layer (research 01, Point in region; tests 5
and 6, note test 6)."""

import math

import numpy as np
import pytest

from geometry2d_checks import loop, polygon, reversed_loop
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows, PointLocation, point_in_region

IN, OUT, ON = PointLocation.IN, PointLocation.OUT, PointLocation.ON
NAN = math.nan
TINY = 2.0**-49  # one rounding unit at 10 and at 15
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def _square_with_semicircle(sweep: float) -> list[list[float]]:
    return [
        [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0],
        [10.0, 0.0, 10.0, 10.0, 10.0, 5.0, sweep],
        [10.0, 10.0, 0.0, 10.0, NAN, NAN, 0.0],
        [0.0, 10.0, 0.0, 0.0, NAN, NAN, 0.0],
    ]


def _both(rows: list[list[float]], ctx: Context) -> list[CurveRows]:
    return [loop(rows, ctx), loop(reversed_loop(rows), ctx)]


def _located(q: list[tuple[float, float]], loops: CurveRows, ctx: Context) -> list[PointLocation]:
    return [PointLocation(v) for v in point_in_region(np.array(q), loops, ctx)]


@pytest.mark.req("REQ-G2D-134", "REQ-G2D-148", "REQ-G2D-149", "REQ-G2D-150")
def test_research_test_5_tolerance_layer(ctx: Context) -> None:
    q = [
        (15.0, 5.0),
        (15.0 - TINY, 5.0),
        (15.0 + TINY, 5.0),
        (15.0 - 2e-6, 5.0),
        (15.0 + 2e-6, 5.0),
        (10.0, 5.0),  # on the chord line
        (5.0, 5.0),  # on the arc's circle, outside its sweep
    ]
    for loops in _both(_square_with_semicircle(math.pi), ctx):
        assert _located(q, loops, ctx) == [ON, ON, ON, IN, OUT, IN, IN]
    for loops in _both(_square_with_semicircle(-math.pi), ctx):
        assert _located([(10.0, 5.0), (4.0, 5.0), (6.0, 5.0)], loops, ctx) == [OUT, IN, OUT]


@pytest.mark.req("REQ-G2D-134", "REQ-G2D-148", "REQ-G2D-149", "REQ-G2D-150")
def test_research_test_6_and_note_test_6(ctx: Context) -> None:
    circle = [[5.0, 0.0, 5.0, 0.0, 0.0, 0.0, math.tau]]
    q = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (0.0, 5.0), (0.0, -3.0)]
    for loops in _both(circle, ctx):
        assert _located(q, loops, ctx) == [IN, ON, OUT, ON, IN]
    q = [(10.0, 5.0), (10.0, 10.0), (10.0 - TINY, 5.0), (10.0 + TINY, 5.0)]
    for loops in [polygon(SQUARE, ctx), polygon(SQUARE[::-1], ctx)]:
        assert _located(q, loops, ctx) == [ON, ON, ON, ON]


@pytest.mark.req("REQ-G2D-148")
def test_eps_len_itself_is_on(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    below = math.nextafter(-eps, -math.inf)
    q = [(5.0, -eps), (5.0, below), (5.0, eps), (5.0, math.nextafter(eps, math.inf))]
    assert _located(q, polygon(SQUARE, ctx), ctx) == [ON, OUT, ON, IN]


@pytest.mark.req("REQ-G2D-148", "REQ-G2D-149")
def test_winding_sums_over_all_loops(ctx: Context) -> None:
    one = polygon(SQUARE, ctx)
    two = polygon([(3.0, 3.0), (3.0, 7.0), (7.0, 7.0), (7.0, 3.0)], ctx)  # a clockwise hole
    loops = CurveRows(
        np.vstack([one.rows, two.rows]), np.arange(8, dtype=np.int64), np.array([0, 4], np.int64)
    )
    q = [(1.0, 1.0), (5.0, 5.0), (3.0, 5.0), (11.0, 5.0), (3.0 - 5e-7, 5.0)]
    assert _located(q, loops, ctx) == [IN, OUT, ON, OUT, ON]


@pytest.mark.req("REQ-G2D-148", "REQ-G2D-150")
def test_the_tolerance_layer_measures_to_the_nearer_radius(ctx: Context) -> None:
    # P1 lies 7e-7 inside the circle of radius |P0 - C| = 5: q at radius 5 + 0.5e-6 is within
    # eps_len of that circle and 1.2e-6 from |P1 - C|; both orientations say ON (Peter,
    # 2026-10-03).
    p1 = (0.0, 5.0 - 7e-7)
    rows = [
        [5.0, 0.0, *p1, 0.0, 0.0, math.pi / 2],
        [*p1, 0.0, 0.0, NAN, NAN, 0.0],
        [0.0, 0.0, 5.0, 0.0, NAN, NAN, 0.0],
    ]
    r = 5.0 + 0.5e-6
    q = [(r * math.cos(0.7), r * math.sin(0.7)), (4.0 * math.cos(0.7), 4.0 * math.sin(0.7))]
    for loops in _both(rows, ctx):
        assert _located(q, loops, ctx) == [ON, IN]


@pytest.mark.req("REQ-G2D-150")
@pytest.mark.parametrize(
    ("rows", "q"),
    [
        (  # a tiny arc whose P1 lies just clockwise of P0
            [
                [5.0, 0.0, 5.0, -1e-8, 0.0, 0.0, 1e-9],
                [5.0, -1e-8, 20.0, 0.0, NAN, NAN, 0.0],
                [20.0, 0.0, 5.0, 10.0, NAN, NAN, 0.0],
                [5.0, 10.0, 5.0, 0.0, NAN, NAN, 0.0],
            ],
            [(3.0, 4.0), (-5.0, 0.0), (6.0, 1.0)],
        ),
        (  # P1 outward near the top of a circle of radius 1000 mm
            [
                [1000.0, 0.0, 0.02, 1000.0000005, 0.0, 0.0, math.atan2(1000.0000005, 0.02)],
                [0.02, 1000.0000005, 0.0, 0.0, NAN, NAN, 0.0],
                [0.0, 0.0, 1000.0, 0.0, NAN, NAN, 0.0],
            ],
            [(0.01, 1000.0000002), (500.0, 500.0), (800.0, 800.0)],
        ),
    ],
)
def test_both_orientations_agree(
    ctx: Context, rows: list[list[float]], q: list[tuple[float, float]]
) -> None:
    forward, backward = _both(rows, ctx)
    assert _located(q, forward, ctx) == _located(q, backward, ctx)
    if len(rows) == 4:  # the tiny arc: its circle off the sweep is not ON
        assert _located(q, forward, ctx) == [OUT, OUT, IN]


@pytest.mark.req("REQ-G2D-134", "REQ-G2D-201")
def test_results_are_int8_read_only_and_one_per_point(ctx: Context) -> None:
    result = point_in_region(
        np.array([[5.0, 5.0], [11.0, 5.0], [0.0, 0.0]]), polygon(SQUARE, ctx), ctx
    )
    assert result.dtype == np.int8
    assert not result.flags.writeable
    assert result.tolist() == [IN, OUT, ON]
    with pytest.raises(ValueError, match="finite"):
        point_in_region(np.array([[math.nan, 1.0]]), polygon(SQUARE, ctx), ctx)


@pytest.mark.req("REQ-G2D-231")
def test_results_are_bit_identical_when_repeated(ctx: Context) -> None:
    q = np.random.default_rng(3).uniform(-2.0, 17.0, size=(500, 2))
    loops = loop(_square_with_semicircle(math.pi), ctx)
    first = point_in_region(q, loops, ctx)
    assert point_in_region(q, loops, ctx).tobytes() == first.tobytes()
