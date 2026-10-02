# SPDX-License-Identifier: Apache-2.0
"""Unit tests for DXF bulge conversion (research 01, Curves; test 8)."""

import math

import pytest

from geometry2d_checks import codes
from splintercam.foundation import Context
from splintercam.geometry2d import Arc, Line, arc_from_bulge, bulges_from_arc, make_arc


def _arc(p0: tuple[float, float], p1: tuple[float, float], bulge: float, ctx: Context) -> Arc:
    result = arc_from_bulge(p0, p1, bulge, ctx)
    assert result.ok, result.diagnostics
    assert isinstance(result.value, Arc)
    return result.value


@pytest.mark.req("REQ-G2D-050")
@pytest.mark.parametrize(
    ("bulge", "centre", "radius", "sweep"),
    [
        (1.0, (1.0, 0.0), 1.0, math.pi),
        (-1.0, (1.0, 0.0), 1.0, -math.pi),
        (math.tan(math.pi / 8), (1.0, 1.0), math.sqrt(2.0), math.pi / 2),
    ],
)
def test_research_test_8(
    ctx: Context, bulge: float, centre: tuple[float, float], radius: float, sweep: float
) -> None:
    arc = _arc((0.0, 0.0), (2.0, 0.0), bulge, ctx)
    assert (arc.p0, arc.p1) == ((0.0, 0.0), (2.0, 0.0))  # end points as given (REQ-G2D-039)
    assert math.dist(arc.centre, centre) <= 1e-15
    assert arc.radius_mm == pytest.approx(radius, abs=1e-15)
    assert arc.sweep_rad == pytest.approx(sweep, abs=1e-15)


@pytest.mark.req("REQ-G2D-050")
@pytest.mark.parametrize(
    ("p0", "p1", "bulge"),
    [
        ((1.0, 1.0), (1.0, 1.0), 0.5),  # a bulge on a zero chord
        ((math.nan, 0.0), (1.0, 0.0), 0.5),
        ((0.0, 0.0), (math.inf, 0.0), 0.5),
        ((0.0, 0.0), (1.0, 0.0), math.nan),
        ((0.0, 0.0), (1.0, 0.0), math.inf),
    ],
)
def test_zero_chord_and_non_finite_values_are_curve_invalid(
    ctx: Context, p0: tuple[float, float], p1: tuple[float, float], bulge: float
) -> None:
    result = arc_from_bulge(p0, p1, bulge, ctx)
    assert result.value is None
    assert codes(result) == ["CURVE_INVALID"]


@pytest.mark.req("REQ-G2D-051")
@pytest.mark.parametrize("bulge", [0.0, -0.0, 1e-9])
def test_zero_bulge_or_a_sagitta_within_eps_len_is_a_line(ctx: Context, bulge: float) -> None:
    # On a 1 mm chord the bulge 1e-9 has the sagitta 5e-10 mm.
    result = arc_from_bulge((0.0, 0.0), (1.0, 0.0), bulge, ctx)
    assert result.ok
    assert result.value == Line((0.0, 0.0), (1.0, 0.0))


@pytest.mark.req("REQ-G2D-051")
def test_sagitta_just_above_eps_len_is_an_arc(ctx: Context) -> None:
    assert isinstance(_arc((0.0, 0.0), (1.0, 0.0), 2.1e-6, ctx), Arc)


@pytest.mark.req("REQ-G2D-052")
@pytest.mark.parametrize("bulge", [1.0, -1.0, math.tan(math.pi / 8), -0.3])
def test_an_arc_gives_back_its_bulge(ctx: Context, bulge: float) -> None:
    arc = _arc((0.0, 0.0), (2.0, 0.0), bulge, ctx)
    ((same, exported),) = bulges_from_arc(arc, ctx)
    assert same == arc
    assert exported == pytest.approx(bulge, rel=1e-15)


@pytest.mark.req("REQ-G2D-053")
@pytest.mark.parametrize("sweep", [math.tau, -math.tau])
def test_full_circle_becomes_two_half_arcs(ctx: Context, sweep: float) -> None:
    # The circle of research 01, test 6.
    circle = Arc((5.0, 0.0), (5.0, 0.0), (0.0, 0.0), sweep)
    (first, b1), (second, b2) = bulges_from_arc(circle, ctx)
    assert first.p0 == circle.p0
    assert second.p0 == first.p1  # bit for bit
    assert second.p1 == circle.p0
    assert first.p1 == (-5.0, 0.0)  # split at the angle sweep / 2
    assert b1 == b2 == math.copysign(1.0, sweep)
    for half in (first, second):
        assert make_arc(half.p0, half.p1, half.centre, half.sweep_rad, ctx).value == (half,)


@pytest.mark.req("REQ-G2D-052", "REQ-G2D-053")
def test_a_tiny_arc_with_equal_end_points_is_not_split(ctx: Context) -> None:
    # make_arc accepts P0 = P1 with a sweep whose arc length is within eps_len; it is no circle.
    built = make_arc((10.0, 0.0), (10.0, 0.0), (0.0, 0.0), 1e-9, ctx)
    assert built.value is not None
    (tiny,) = built.value
    assert isinstance(tiny, Arc)
    assert bulges_from_arc(tiny, ctx) == ((tiny, math.tan(1e-9 / 4)),)


@pytest.mark.req("REQ-G2D-050")
def test_a_huge_bulge_does_not_overflow(ctx: Context) -> None:
    # |b| = 1e200: b*b overflows, (1/b - b)/4 does not; the arc is all but a full circle.
    result = arc_from_bulge((0.0, 0.0), (1.0, 0.0), 1e200, ctx)
    assert codes(result) != ["CURVE_INVALID"]
