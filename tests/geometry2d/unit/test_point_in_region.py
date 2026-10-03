# SPDX-License-Identifier: Apache-2.0
"""Unit tests for point in region (research 01, Point in region; tests 5 and 6, note test 6)."""

import math

import numpy as np
import pytest

from geometry2d_checks import loop, polygon, reversed_loop
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows, PointLocation, point_in_region
from splintercam.geometry2d._region import point_in_region_exact

IN, OUT, ON = PointLocation.IN, PointLocation.OUT, PointLocation.ON
NAN = math.nan


def _square_with_semicircle(sweep: float) -> list[list[float]]:
    # The square [0, 10]² whose right side is a semicircle about (10, 5): outward for φ = +π,
    # inward for φ = -π (research 01, tests 3 and 5).
    return [
        [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0],
        [10.0, 0.0, 10.0, 10.0, 10.0, 5.0, sweep],
        [10.0, 10.0, 0.0, 10.0, NAN, NAN, 0.0],
        [0.0, 10.0, 0.0, 0.0, NAN, NAN, 0.0],
    ]


BULGED = _square_with_semicircle(math.pi)
BITTEN = _square_with_semicircle(-math.pi)
CIRCLE = [[5.0, 0.0, 5.0, 0.0, 0.0, 0.0, math.tau]]
SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
TINY = 2.0**-49  # one rounding unit at 10 and at 15


def _both_orientations(rows: list[list[float]], ctx: Context) -> list[CurveRows]:
    return [loop(rows, ctx), loop(reversed_loop(rows), ctx)]


def _exact(q: list[tuple[float, float]], loops: CurveRows) -> list[PointLocation]:
    return [PointLocation(v) for v in point_in_region_exact(np.array(q), loops)]


def _located(q: list[tuple[float, float]], loops: CurveRows, ctx: Context) -> list[PointLocation]:
    return [PointLocation(v) for v in point_in_region(np.array(q), loops, ctx)]


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139", "REQ-G2D-143", "REQ-G2D-145", "REQ-G2D-150")
def test_research_test_5_exact_layer(ctx: Context) -> None:
    q = [(15.0, 5.0), (15.0 - TINY, 5.0), (15.0 + TINY, 5.0), (10.0, 5.0), (5.0, 5.0)]
    for loops in _both_orientations(BULGED, ctx):
        assert _exact(q, loops) == [ON, IN, OUT, IN, IN]


@pytest.mark.req("REQ-G2D-134", "REQ-G2D-148", "REQ-G2D-149", "REQ-G2D-150")
def test_research_test_5_tolerance_layer(ctx: Context) -> None:
    q = [
        (15.0, 5.0),
        (15.0 - TINY, 5.0),
        (15.0 + TINY, 5.0),
        (15.0 - 2e-6, 5.0),
        (15.0 + 2e-6, 5.0),
    ]
    for loops in _both_orientations(BULGED, ctx):
        assert _located(q, loops, ctx) == [ON, ON, ON, IN, OUT]


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-149", "REQ-G2D-150")
def test_research_test_5_inward_semicircle(ctx: Context) -> None:
    for loops in _both_orientations(BITTEN, ctx):
        assert _located([(10.0, 5.0), (4.0, 5.0), (6.0, 5.0)], loops, ctx) == [OUT, IN, OUT]


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-143", "REQ-G2D-150")
def test_research_test_6_full_circle(ctx: Context) -> None:
    q = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (0.0, 5.0), (0.0, -3.0), (0.0, -5.0), (-5.0, 0.0)]
    for loops in _both_orientations(CIRCLE, ctx):
        expected = [IN, ON, OUT, ON, IN, ON, ON]
        assert _exact(q, loops) == expected
        assert _located(q, loops, ctx) == expected


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139", "REQ-G2D-143", "REQ-G2D-148", "REQ-G2D-150")
def test_shewchuk_note_test_6_square(ctx: Context) -> None:
    q = [(10.0, 5.0), (10.0, 10.0), (10.0 - TINY, 5.0), (10.0 + TINY, 5.0)]
    for loops in [polygon(SQUARE, ctx), polygon(SQUARE[::-1], ctx)]:
        assert _exact(q, loops) == [ON, ON, IN, OUT]
        assert _located(q, loops, ctx) == [ON, ON, ON, ON]


@pytest.mark.req("REQ-G2D-135")
def test_rays_through_vertices_count_once(ctx: Context) -> None:
    # Rays at the height of a vertex: the half-open ranges count each crossing once.
    diamond = polygon([(0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0)], ctx)
    q = [(-2.0, 0.0), (-0.5, 0.0), (0.5, 0.0), (2.0, 0.0), (0.0, 1.0), (0.0, -1.0), (0.0, 2.0)]
    assert _exact(q, diamond) == [OUT, IN, IN, OUT, ON, ON, OUT]


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139")
def test_rays_at_the_top_and_bottom_of_an_arc(ctx: Context) -> None:
    # The heights c_y ± r of the full circle are doubles here: rays tangent at them miss it.
    for loops in _both_orientations(CIRCLE, ctx):
        assert _exact([(-7.0, 5.0), (-7.0, -5.0), (7.0, 5.0), (-7.0, 5.0 - TINY)], loops) == [
            OUT,
            OUT,
            OUT,
            OUT,
        ]
        assert _exact([(0.0, 5.0 - 2.0**-40), (0.0, -5.0 + 2.0**-40)], loops) == [IN, IN]


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139", "REQ-G2D-143")
@pytest.mark.parametrize("start", [0.3, 1.0, 2.0, 3.5, 4.0, 5.5, -0.2])
def test_arcs_split_at_their_top_and_bottom(ctx: Context, start: float) -> None:
    # A three-quarter circle closed by its chord, starting at various angles: points well inside
    # the arc part, inside the triangle part, outside the chord and outside the circle.
    r = 4.0
    sweep = 1.5 * math.pi
    p0 = (r * math.cos(start), r * math.sin(start))
    p1 = (r * math.cos(start + sweep), r * math.sin(start + sweep))
    rows = [[*p0, *p1, 0.0, 0.0, sweep], [*p1, *p0, NAN, NAN, 0.0]]
    middle = start + sweep / 2  # inside the arc part, opposite the chord
    gap = start - math.pi / 4  # the middle of the missing quarter
    q = [
        (0.5 * r * math.cos(middle), 0.5 * r * math.sin(middle)),
        (0.95 * r * math.cos(middle), 0.95 * r * math.sin(middle)),
        (0.9 * r * math.cos(gap), 0.9 * r * math.sin(gap)),
        (1.2 * r * math.cos(middle), 1.2 * r * math.sin(middle)),
        (0.0, 0.0),
    ]
    for loops in _both_orientations(rows, ctx):
        assert _exact(q, loops) == [IN, IN, OUT, OUT, IN]


@pytest.mark.req("REQ-G2D-134", "REQ-G2D-149")
def test_winding_sums_over_all_loops(ctx: Context) -> None:
    # A square with a square hole of the opposite orientation: inside the hole the winding is 0.
    outer = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    hole = [(3.0, 3.0), (3.0, 7.0), (7.0, 7.0), (7.0, 3.0)]
    one, two = polygon(outer, ctx), polygon(hole, ctx)
    loops = CurveRows(
        np.vstack([one.rows, two.rows]),
        np.arange(8, dtype=np.int64),
        np.array([0, 4], dtype=np.int64),
    )
    assert _located([(1.0, 1.0), (5.0, 5.0), (3.0, 5.0), (11.0, 5.0)], loops, ctx) == [
        IN,
        OUT,
        ON,
        OUT,
    ]


@pytest.mark.req("REQ-G2D-134")
def test_results_are_int8_and_one_per_point(ctx: Context) -> None:
    result = point_in_region(np.zeros((3, 2)), polygon(SQUARE, ctx), ctx)
    assert result.dtype == np.int8
    assert result.tolist() == [ON, ON, ON]
    with pytest.raises(ValueError, match="finite"):
        point_in_region(np.array([[math.nan, 1.0]]), polygon(SQUARE, ctx), ctx)


@pytest.mark.req("REQ-G2D-231")
def test_results_are_bit_identical_when_repeated(ctx: Context) -> None:
    q = np.random.default_rng(3).uniform(-2.0, 17.0, size=(500, 2))
    loops = loop(BULGED, ctx)
    first = point_in_region(q, loops, ctx)
    assert point_in_region(q, loops, ctx).tobytes() == first.tobytes()


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-150")
def test_an_arc_whose_p1_lies_past_the_top_leaves_no_gap(ctx: Context) -> None:
    # Found by the flattening property: a half disc whose arc ends 2^-126 mm above the top of its
    # circle (P1 may lie off the circle, REQ-G2D-042). The ray at the height of the top must meet
    # the boundary an even number of times left of the disc.
    rows = [
        [0.0, 2.0**-126, 0.0, -1.0, NAN, NAN, 0.0],
        [0.0, -1.0, 0.0, 2.0**-126, 0.0, -0.5, math.pi],
    ]
    for loops in _both_orientations(rows, ctx):
        assert _exact([(-1.0, 0.0), (0.25, 0.0), (0.25, -0.5), (1.0, 0.0)], loops) == [
            OUT,
            OUT,
            IN,
            OUT,
        ]
