# SPDX-License-Identifier: Apache-2.0
"""Property test: the signed area of a polygon against exact rationals (research 01, Area and
orientation)."""

import math
from fractions import Fraction

import pytest
from hypothesis import HealthCheck, assume, given, reject, settings
from hypothesis import strategies as st

import geometry2d_oracles as oracle
from geometry2d_checks import polygon
from splintercam.foundation import Context
from splintercam.geometry2d import signed_area

U = 2.0**-53  # the unit roundoff of binary64
# Unit coordinates on a 2^-20 grid: no tiny values below the predicates' input range to filter.
GRID = st.integers(-(2**20), 2**20).map(lambda k: k / 2**20)


# The ctx fixture holds a progress log and a debug sink that every example shares; signed_area
# uses neither, so sharing it is safe here.
@pytest.mark.req("REQ-G2D-001", "REQ-G2D-128", "REQ-G2D-130", "REQ-G2D-131", "REQ-G2D-133")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    offset=st.tuples(st.floats(-1e4, 1e4), st.floats(-1e4, 1e4)),
    half_extent=st.floats(1e-3, 3355.0),
    unit_points=st.lists(
        st.tuples(st.floats(-1.0, 1.0), st.floats(-1.0, 1.0)), min_size=3, max_size=40
    ),
)
def test_the_float_sum_keeps_the_sign_and_the_bound(
    ctx: Context,
    offset: tuple[float, float],
    half_extent: float,
    unit_points: list[tuple[float, float]],
) -> None:
    points = [(offset[0] + half_extent * x, offset[1] + half_extent * y) for x, y in unit_points]
    # The bound does not model underflow: keep to the predicates' input range (a precondition).
    assume(all(oracle.in_safe_range(*p) for p in points))
    exact = oracle.polygon_area(points)
    length = sum(math.dist(p, q) for p, q in zip(points, points[1:] + points[:1], strict=True))
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    e = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    n = len(points)
    # Research 01's bound for the sums, plus the rounding of the translation itself: each
    # translated coordinate is off by at most u·(E + u·|centre|), moving the area by twice that
    # times L at most.
    largest = max(abs(v) for p in points for v in p)
    bound = n * U * (math.sqrt(2) * e * length + 3 * e * e) + 2 * U * (e + U * largest) * length
    eps_l = ctx.tolerances.length_eps_mm * length
    result = signed_area(polygon(points, ctx), ctx)
    if abs(exact) > eps_l + bound:
        assert result.value is not None
        assert (result.value > 0) == (exact > 0)
        assert abs(Fraction(result.value) - exact) <= Fraction(bound)
    elif abs(exact) < eps_l - bound:
        assert result.value is None


@pytest.mark.req("REQ-G2D-002")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    half_extent=st.floats(1.0, 5000.0),  # both paths: the limit is 3355 mm
    unit_points=st.lists(st.tuples(GRID, GRID), min_size=3, max_size=40),
)
def test_reversal_negates_the_area(
    ctx: Context, half_extent: float, unit_points: list[tuple[float, float]]
) -> None:
    points = [(half_extent * x, half_extent * y) for x, y in unit_points]
    forward = signed_area(polygon(points, ctx), ctx).value
    backward = signed_area(polygon(points[::-1], ctx), ctx).value
    if forward is None:  # a degenerate loop: nothing to negate
        reject()
    assert backward is not None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    e = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    if e > 3355.0:  # the exact path: the doubled terms negate exactly
        assert backward == -forward
        return
    length = sum(math.dist(p, q) for p, q in zip(points, points[1:] + points[:1], strict=True))
    n = len(points)
    # Each direction is within research 01's bound of the same exact value.
    bound = n * U * (math.sqrt(2) * e * length + 3 * e * e)
    assert abs(backward + forward) <= 2 * bound
