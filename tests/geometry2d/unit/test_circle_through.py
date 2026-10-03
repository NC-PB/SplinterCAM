# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the circle through three points (research 01, Circle through three points;
test 9 and test 5 of the Shewchuk note)."""

import math
import warnings

import pytest

import geometry2d_oracles as oracle
from splintercam.foundation import Context
from splintercam.geometry2d import Circle, circle_through, orient2d


@pytest.mark.req("REQ-G2D-097")
def test_shewchuk_note_test_5_centre_is_exact(ctx: Context) -> None:
    assert circle_through((0.0, 0.0), (4.0, 0.0), (0.0, 2.0), ctx) == Circle(
        (2.0, 1.0), math.sqrt(5.0)
    )


@pytest.mark.req("REQ-G2D-098")
def test_collinear_points_give_no_circle(ctx: Context) -> None:
    assert circle_through((0.0, 0.0), (1.0, 1.0), (2.0, 2.0), ctx) is None


@pytest.mark.req("REQ-G2D-099")
def test_a_point_within_eps_len_of_the_line_gives_no_circle(ctx: Context) -> None:
    p1, p2, p3 = (0.0, 0.0), (1.0, 1.0 + 2.0**-52), (2.0, 2.0)
    assert orient2d([p1], [p2], [p3])[0] != 0  # not collinear: the line-distance rule decides
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert circle_through(p1, p2, p3, ctx) is None


@pytest.mark.req("REQ-G2D-099")
def test_eps_len_is_the_boundary(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    # P2 at 2·eps_len, then at eps_len / 2, from the line y = 0 through P1 and P3.
    assert circle_through((0.0, 0.0), (1.0, 2 * eps), (2.0, 0.0), ctx) is not None
    assert circle_through((0.0, 0.0), (1.0, eps / 2), (2.0, 0.0), ctx) is None


@pytest.mark.req("REQ-G2D-100")
def test_p1_equal_to_p3_gives_no_circle(ctx: Context) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert circle_through((1.0, 2.0), (4.0, 6.0), (1.0, 2.0), ctx) is None


@pytest.mark.req("REQ-G2D-097", "REQ-G2D-101")
def test_a_short_chord_still_gives_its_circle(ctx: Context) -> None:
    # Research 01, test 9: P1P3 is only 0.001 mm long, P2 lies across the circle.
    p1, p2 = (10.0, 0.0), (-10.0, 0.0)
    p3 = (10 * math.cos(-1e-4), 10 * math.sin(-1e-4))
    assert math.dist(p1, p3) == pytest.approx(0.001, rel=1e-6)
    circle = circle_through(p1, p2, p3, ctx)
    assert circle is not None
    cx, cy = oracle.circumcentre(p1, p2, p3)
    assert circle.centre == pytest.approx((float(cx), float(cy)), abs=1e-12)
    assert circle.radius_mm == pytest.approx(10.0, abs=1e-12)


@pytest.mark.req("REQ-G2D-101")
def test_no_radius_limit_of_its_own(ctx: Context) -> None:
    p1, p2, p3 = (0.0, 0.0), (1000.0, 0.01), (2000.0, 0.0)
    circle = circle_through(p1, p2, p3, ctx)
    assert circle is not None
    assert circle.radius_mm == pytest.approx((1000.0**2 + 0.01**2) / 0.02, rel=1e-9)


@pytest.mark.req("REQ-G2D-097")
def test_radius_is_the_distance_to_p1(ctx: Context) -> None:
    p1 = (0.3, 0.1)
    circle = circle_through(p1, (4.7, 0.2), (0.4, 2.9), ctx)
    assert circle is not None
    assert circle.radius_mm == math.dist(p1, circle.centre)


def test_a_non_finite_point_is_a_programming_error(ctx: Context) -> None:
    with pytest.raises(ValueError, match="finite"):
        circle_through((0.0, 0.0), (math.nan, 1.0), (2.0, 0.0), ctx)
