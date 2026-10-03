# SPDX-License-Identifier: Apache-2.0
"""Property tests: closest points and circles through three points against exact rationals and
brute force (research 01, Distances and closest points, Circle through three points)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

import geometry2d_oracles as oracle
from splintercam.foundation import Context
from splintercam.geometry2d import Arc, Line, circle_through, closest_point

coordinate = st.floats(-1000.0, 1000.0)
point = st.tuples(coordinate, coordinate)
# The ctx fixture holds a progress log and a debug sink that every example shares; these
# functions use neither, so sharing it is safe here.
shared_ctx = settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)


@pytest.mark.req("REQ-G2D-091")
@shared_ctx
@given(q=point, p0=point, p1=point)
def test_line_foot_matches_the_exact_foot(
    ctx: Context, q: tuple[float, float], p0: tuple[float, float], p1: tuple[float, float]
) -> None:
    assume(p0 != p1)
    found = closest_point(Line(p0, p1), q, ctx)
    t, fx, fy = oracle.line_foot(q, p0, p1)
    scale = max(1.0, *map(abs, (*q, *p0, *p1)))
    assert found.parameter == pytest.approx(float(t), abs=1e-12 * scale / math.dist(p0, p1))
    assert found.point == pytest.approx((float(fx), float(fy)), abs=1e-12 * scale)


@pytest.mark.req("REQ-G2D-093", "REQ-G2D-094")
@shared_ctx
@given(
    r=st.floats(0.1, 100.0),
    start=st.floats(-math.pi, math.pi),
    sweep=st.floats(0.01, math.tau).flatmap(lambda s: st.sampled_from([s, -s])),
    q=point,
)
def test_arc_closest_point_is_no_farther_than_any_arc_point(
    ctx: Context, r: float, start: float, sweep: float, q: tuple[float, float]
) -> None:
    centre = (1.0, -2.0)
    p0 = (centre[0] + r * math.cos(start), centre[1] + r * math.sin(start))
    p1 = (centre[0] + r * math.cos(start + sweep), centre[1] + r * math.sin(start + sweep))
    found = closest_point(Arc(p0, p1, centre, sweep), q, ctx)
    assert found.distance_mm == pytest.approx(math.dist(q, found.point), abs=1e-9)
    assert 0.0 <= found.parameter <= abs(sweep)
    angles = start + np.linspace(0.0, sweep, 2001)
    samples = np.column_stack((centre[0] + r * np.cos(angles), centre[1] + r * np.sin(angles)))
    nearest = float(np.min(np.hypot(samples[:, 0] - q[0], samples[:, 1] - q[1])))
    assert found.distance_mm <= nearest + 1e-9 * max(1.0, nearest)
    # The point found lies on the arc: on its circle, at its parameter from P0.
    assert math.dist(found.point, centre) == pytest.approx(r, abs=1e-9)
    direction = start + math.copysign(found.parameter, sweep)
    expected = (centre[0] + r * math.cos(direction), centre[1] + r * math.sin(direction))
    assert found.point == pytest.approx(expected, abs=1e-9)


@pytest.mark.req("REQ-G2D-097", "REQ-G2D-099")
@shared_ctx
@given(p1=point, p2=point, p3=point)
def test_circle_matches_the_exact_circumcentre(
    ctx: Context, p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]
) -> None:
    chord = math.dist(p1, p3)
    assume(chord > 0.0)
    height = abs(oracle.twice_area(p1, p2, p3)) / chord  # P2's distance from the line P1P3
    circle = circle_through(p1, p2, p3, ctx)
    if height <= 0.5 * ctx.tolerances.length_eps_mm:
        assert circle is None
        return
    # Clear of the eps_len boundary, and well conditioned: P2 not much closer to the line than a
    # tenth of the chord.
    assume(height >= max(2 * ctx.tolerances.length_eps_mm, 0.1 * chord))
    assert circle is not None
    cx, cy = oracle.circumcentre(p1, p2, p3)
    scale = max(1.0, *map(abs, (*p1, *p2, *p3)), circle.radius_mm)
    assert circle.centre == pytest.approx((float(cx), float(cy)), abs=1e-12 * scale)
