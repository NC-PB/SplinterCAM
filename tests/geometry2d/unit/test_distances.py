# SPDX-License-Identifier: Apache-2.0
"""Unit tests for closest points on lines and arcs (research 01, Distances and closest points;
test 17)."""

import math

import pytest

from splintercam.foundation import Context
from splintercam.geometry2d import Arc, ClosestPoint, Line, closest_point

QUARTER = Arc((5.0, 0.0), (0.0, 5.0), (0.0, 0.0), math.pi / 2)  # CCW, from +x to +y
QUARTER_CW = Arc((0.0, 5.0), (5.0, 0.0), (0.0, 0.0), -math.pi / 2)  # the same points, CW


def _close(found: ClosestPoint, point: tuple[float, float], parameter: float, d: float) -> None:
    assert found.point == pytest.approx(point, abs=1e-12)
    assert found.parameter == pytest.approx(parameter, abs=1e-12)
    assert found.distance_mm == pytest.approx(d, abs=1e-12)


@pytest.mark.req("REQ-G2D-091")
@pytest.mark.parametrize(
    ("q", "point", "t", "d"),
    [
        ((3.0, 4.0), (3.0, 0.0), 0.3, 4.0),  # foot inside
        ((-2.0, 1.0), (0.0, 0.0), 0.0, math.sqrt(5.0)),  # before P0
        ((12.0, -1.0), (10.0, 0.0), 1.0, math.sqrt(5.0)),  # beyond P1
    ],
)
def test_line_gives_the_clamped_foot(
    ctx: Context, q: tuple[float, float], point: tuple[float, float], t: float, d: float
) -> None:
    _close(closest_point(Line((0.0, 0.0), (10.0, 0.0)), q, ctx), point, t, d)


@pytest.mark.req("REQ-G2D-091")
def test_clamped_feet_are_the_end_points_exactly(ctx: Context) -> None:
    line = Line((0.1, 0.7), (3.3, -2.9))
    assert closest_point(line, (-5.0, 3.0), ctx).point == line.p0
    assert closest_point(line, (9.0, -8.0), ctx).point == line.p1


@pytest.mark.req("REQ-G2D-092")
def test_zero_length_line_is_its_point(ctx: Context) -> None:
    assert closest_point(Line((1.0, 1.0), (1.0, 1.0)), (4.0, 5.0), ctx) == ClosestPoint(
        (1.0, 1.0), 0.0, 5.0
    )


@pytest.mark.req("REQ-G2D-093")
@pytest.mark.parametrize(
    ("arc", "q", "point", "parameter", "d"),
    [
        (QUARTER, (6.0, 8.0), (3.0, 4.0), math.atan2(8.0, 6.0), 5.0),  # outside the circle
        (QUARTER, (1.0, 1.0), (5 / math.sqrt(2), 5 / math.sqrt(2)), math.pi / 4, 5 - math.sqrt(2)),
        (QUARTER, (0.0, 7.0), (0.0, 5.0), math.pi / 2, 2.0),  # on the ray of P1
        (QUARTER_CW, (6.0, 8.0), (3.0, 4.0), math.atan2(6.0, 8.0), 5.0),  # parameter in φ's sense
    ],
)
def test_arc_inside_the_sweep_gives_the_radial_point(  # noqa: PLR0913 (parametrized)
    ctx: Context,
    arc: Arc,
    q: tuple[float, float],
    point: tuple[float, float],
    parameter: float,
    d: float,
) -> None:
    _close(closest_point(arc, q, ctx), point, parameter, d)


@pytest.mark.req("REQ-G2D-093")
@pytest.mark.parametrize("arc", [QUARTER, QUARTER_CW])
def test_the_sweep_is_decided_by_exact_signs(ctx: Context, arc: Arc) -> None:
    # 2^-40 mm off the ray through (0, 5): inside the sweep the point moves off the y axis,
    # outside it is P1 or P0 of the CW arc, (0, 5), exactly.
    inside = closest_point(arc, (2.0**-40, 7.0), ctx).point
    assert inside[0] > 0.0
    assert closest_point(arc, (-(2.0**-40), 7.0), ctx).point == (0.0, 5.0)


@pytest.mark.req("REQ-G2D-093")
def test_full_circle_contains_every_direction(ctx: Context) -> None:
    circle = Arc((5.0, 0.0), (5.0, 0.0), (0.0, 0.0), math.tau)
    _close(closest_point(circle, (0.0, -7.0), ctx), (0.0, -5.0), 3 * math.pi / 2, 2.0)
    _close(closest_point(circle, (7.0, -(2.0**-40)), ctx), (5.0, 0.0), math.tau, 2.0)


@pytest.mark.req("REQ-G2D-094")
@pytest.mark.parametrize(
    ("arc", "q", "point", "parameter"),
    [
        (QUARTER, (3.0, -4.0), (5.0, 0.0), 0.0),  # nearer P0
        (QUARTER, (-3.0, 4.0), (0.0, 5.0), math.pi / 2),  # nearer P1
        (QUARTER, (-1.0, -1.0), (5.0, 0.0), 0.0),  # equally near: P0
        (QUARTER_CW, (-1.0, -1.0), (0.0, 5.0), 0.0),  # equally near: P0 of the CW arc
    ],
)
def test_arc_outside_the_sweep_gives_the_nearer_end(
    ctx: Context,
    arc: Arc,
    q: tuple[float, float],
    point: tuple[float, float],
    parameter: float,
) -> None:
    found = closest_point(arc, q, ctx)
    assert found.point == point
    assert found.parameter == parameter
    assert found.distance_mm == math.dist(q, point)


@pytest.mark.req("REQ-G2D-093", "REQ-G2D-094")
def test_the_sweep_governs_when_p1_lies_just_beyond_p0(ctx: Context) -> None:
    # REQ-G2D-043 lets P1 lie up to eps_len / r past where the sweep ends (ours, as in
    # bounding_box): a tiny arc whose P1 is just behind P0 passes no far direction, and a nearly
    # full one whose P1 is just past P0 passes every direction.
    tiny = Arc((5.0, 0.0), (5.0, -1e-7), (0.0, 0.0), 1e-12)
    assert closest_point(tiny, (-7.0, 0.0), ctx).point == (5.0, 0.0)
    nearly_full = Arc((5.0, 0.0), (5.0, 1e-7), (0.0, 0.0), math.tau - 1e-12)
    _close(closest_point(nearly_full, (-7.0, 0.0), ctx), (-5.0, 0.0), math.pi, 2.0)


@pytest.mark.req("REQ-G2D-096")
@pytest.mark.parametrize("arc", [QUARTER, QUARTER_CW])
def test_centre_gives_p0_at_the_radius(ctx: Context, arc: Arc) -> None:
    assert closest_point(arc, (0.0, 0.0), ctx) == ClosestPoint(arc.p0, 0.0, 5.0)
