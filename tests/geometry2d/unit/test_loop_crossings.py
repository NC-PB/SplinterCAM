# SPDX-License-Identifier: Apache-2.0
"""Unit tests for crossings between loops (research 01, Loop tree, rule 4; test 7; REQ-G2D-237)."""

import math

import numpy as np
import pytest

from geometry2d_checks import codes, polygons
from splintercam.foundation import Context
from splintercam.geometry2d import curve_rows
from splintercam.geometry2d._crossings import contact_points
from splintercam.geometry2d._screen import Screened, screen_loops

Points = list[tuple[float, float]]


def _box(x0: float, y0: float, x1: float, y1: float) -> Points:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _screen(loops: list[Points], ctx: Context) -> tuple[Screened, list[str]]:
    result = screen_loops(polygons(loops, ctx), ctx)
    assert result.value is not None
    return result.value, codes(result)


@pytest.mark.req("REQ-G2D-160", "REQ-G2D-161", "REQ-G2D-237", "REQ-G2D-236")
def test_two_crossing_squares_of_research_test_7(ctx: Context) -> None:
    screened, found = _screen([_box(0, 0, 10, 10), _box(5, 5, 15, 15)], ctx)
    assert found == ["LOOPS_CROSS"]
    assert screened.crossing_points.tolist() == [[5.0, 10.0], [10.0, 5.0]]
    assert screened.crossing_loops.tolist() == [[0, 1], [0, 1]]


@pytest.mark.req("REQ-G2D-160", "REQ-G2D-237")
@pytest.mark.parametrize(
    ("base", "other"),
    [
        (_box(0, 0, 10, 10), _box(5, 0, 15, 10)),  # meeting only at vertices and stretches
        (_box(0, 0, 100, 1), _box(29.5, -10, 30.5, 50)),  # a T of slots, 1 mm deep
        (_box(0, 0, 100, 100), _box(95, 10, 105, 20)),  # through one edge
    ],
)
def test_loops_passing_through_each_other_cross(ctx: Context, base: Points, other: Points) -> None:
    _, found = _screen([base, other], ctx)
    assert found == ["LOOPS_CROSS"]


@pytest.mark.req("REQ-G2D-163")
@pytest.mark.parametrize(
    "other",
    [
        _box(0, 4, 2, 6),  # an island touching the outer wall (research 01, test 7)
        _box(0, 0, 5, 5),  # sharing a corner and two edges from inside
        _box(10, 10, 20, 20),  # outside, sharing a vertex
        _box(10.0001, 0, 20, 10),  # outside, a gap between eps_len and t_topo
        _box(10, 2, 20, 8),  # outside, sharing part of an edge
    ],
)
def test_touching_loops_are_accepted(ctx: Context, other: Points) -> None:
    screened, found = _screen([_box(0, 0, 10, 10), other], ctx)
    assert found == []
    assert screened.kept.tolist() == [0, 1]
    assert screened.crossing_points.shape == (0, 2)


@pytest.mark.req("REQ-G2D-237")
@pytest.mark.parametrize(("depth_t_topo", "cross"), [(0.5, False), (1.0, False), (2.0, True)])
def test_a_poke_counts_only_beyond_t_topo(ctx: Context, depth_t_topo: float, cross: bool) -> None:
    t_topo = ctx.tolerances.topology_tol_mm
    poke = _box(5, 2, 10 + depth_t_topo * t_topo, 8)
    _, found = _screen([_box(0, 0, 10, 10), poke], ctx)
    assert found == (["LOOPS_CROSS"] if cross else [])


def _circle(cx: float, r: float, start: float) -> list[float]:
    p = (cx + r * math.cos(start), r * math.sin(start))
    return [*p, *p, cx, 0.0, math.tau]


@pytest.mark.req("REQ-G2D-237", "REQ-G2D-163")
def test_tangent_circles_touch_in_all_88_placements(ctx: Context) -> None:
    crossing_flattenings = 0
    for k in range(44):
        for start in (0.0, math.pi / 7):
            rows = np.array([_circle(0.0, 10.0, k * math.pi / 22), _circle(5.0, 5.0, start)])
            built = curve_rows(rows, np.arange(2, dtype=np.int64), np.array([0, 1], np.int64), ctx)
            assert built.value is not None
            result = screen_loops(built.value, ctx)
            assert result.value is not None
            assert codes(result) == []
            outer, inner = result.value.polylines
            crossing_flattenings += (
                contact_points(outer, inner, ctx.tolerances.topology_tol_mm).shape[0] > 1
            )
    assert crossing_flattenings >= 80  # their flattenings do cross properly (DEC-G2D-024)


@pytest.mark.req("REQ-G2D-237")
def test_a_square_with_its_corner_on_a_circle_touches(ctx: Context) -> None:
    corner = (10 * math.cos(math.pi / 4), 10 * math.sin(math.pi / 4))
    nan = math.nan
    square = _box(0, 0, *corner)
    rows = [_circle(0.0, 10.0, 0.0)] + [
        [*p, *q, nan, nan, 0.0] for p, q in zip(square, square[1:] + square[:1], strict=True)
    ]
    built = curve_rows(
        np.array(rows), np.arange(5, dtype=np.int64), np.array([0, 1], np.int64), ctx
    )
    assert built.value is not None
    result = screen_loops(built.value, ctx)
    assert codes(result) == []


@pytest.mark.req("REQ-G2D-160")
def test_contact_points_find_a_crossing_by_a_tiny_dip() -> None:
    # A triangle dipping 2^-40 mm below the square's bottom edge: two proper crossings, found by
    # exact signs (inside the predicates' range, DEC-G2D-008), though far shallower than t_topo.
    square = np.array(_box(0, 0, 10, 10), dtype=np.float64)
    dip = np.array([(2.0, 5.0), (5.0, -(2.0**-40)), (8.0, 5.0)], dtype=np.float64)
    found = contact_points(square, dip, 1.0)
    assert found.shape == (2, 2)
    np.testing.assert_allclose(found[:, 1], 0.0, atol=1e-11)


@pytest.mark.req("REQ-G2D-160")
def test_contact_points_find_shared_vertices_and_stretches() -> None:
    square = np.array(_box(0, 0, 10, 10), dtype=np.float64)
    corner = np.array(_box(10, 10, 20, 20), dtype=np.float64)
    assert contact_points(square, corner, 1.0).tolist() == [[10.0, 10.0]]
    beside = np.array(_box(10, 2, 20, 8), dtype=np.float64)
    assert contact_points(square, beside, 1.0).tolist() == [[10.0, 2.0], [10.0, 8.0]]
    far = np.array(_box(30, 0, 40, 10), dtype=np.float64)
    assert contact_points(square, far, 1.0).shape == (0, 2)
