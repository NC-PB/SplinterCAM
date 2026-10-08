# SPDX-License-Identifier: Apache-2.0
"""Unit tests of the rule 5 fallback (research 01, Loop tree, rule 5; test 24; REQ-G2D-169 to
172)."""

import pytest

from geometry2d_checks import polygons
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows
from splintercam.geometry2d._contain import contained_by_difference, fallback_inner

Points = list[tuple[float, float]]
SQUARE: Points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]


def _one(points: Points, ctx: Context) -> CurveRows:
    return polygons([points], ctx)


@pytest.mark.req("REQ-G2D-169")
@pytest.mark.parametrize(("apex", "contained"), [((5.0, -1.0), False), ((5.0, 1.0), True)])
def test_the_triangles_of_research_test_24(
    ctx: Context, apex: tuple[float, float], contained: bool
) -> None:
    triangle: Points = [(0.0, 0.0), (10.0, 0.0), apex]
    inside, difference = contained_by_difference(_one(triangle, ctx), _one(SQUARE, ctx), ctx)
    assert inside == contained
    assert difference == pytest.approx(0.0 if contained else 5.0, abs=1e-6)  # all of B, 5 mm²


@pytest.mark.req("REQ-G2D-171")
def test_two_fallback_results_go_to_the_smaller_difference(ctx: Context) -> None:
    wider: Points = [(0.0, 0.0), (10.00015, 0.0), (10.00015, 10.0), (0.0, 10.0)]
    square, rectangle = _one(SQUARE, ctx), _one(wider, ctx)
    assert fallback_inner(square, rectangle, ctx) == 0  # square minus rectangle is empty
    assert fallback_inner(rectangle, square, ctx) == 1


@pytest.mark.req("REQ-G2D-172")
def test_equal_differences_go_to_the_earlier_loop(ctx: Context) -> None:
    shifted: Points = [(0.0001, 0.0), (10.0001, 0.0), (10.0001, 10.0), (0.0001, 10.0)]
    square, other = _one(SQUARE, ctx), _one(shifted, ctx)
    assert fallback_inner(square, other, ctx) == 0
    assert fallback_inner(other, square, ctx) == 0


@pytest.mark.req("REQ-G2D-034", "REQ-G2D-169")
def test_a_fallback_over_the_span_limit_is_refused(ctx: Context) -> None:
    far: Points = [(7000.0, 0.0), (7010.0, 0.0), (7010.0, 10.0), (7000.0, 10.0)]
    with pytest.raises(ValueError, match="REGION_TOO_LARGE"):
        contained_by_difference(_one(far, ctx), _one(SQUARE, ctx), ctx)


@pytest.mark.req("REQ-G2D-033", "REQ-G2D-169")
def test_a_forced_fallback_pair_moved_by_metres_gives_the_same_answer(ctx: Context) -> None:
    notched: Points = [(0, 0), (2, 0), (2, 5), (2.002, 5), (2.002, 0), (10, 0), (10, 10), (0, 10)]

    def moved(points: Points) -> Points:
        return [(x + 3000.0, y - 2500.0) for x, y in points]

    here = contained_by_difference(_one(SQUARE, ctx), _one(notched, ctx), ctx)
    there = contained_by_difference(_one(moved(SQUARE), ctx), _one(moved(notched), ctx), ctx)
    assert here[0] == there[0] is True
    assert there[1] == pytest.approx(here[1], abs=1e-6)
