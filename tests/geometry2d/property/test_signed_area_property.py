# SPDX-License-Identifier: Apache-2.0
"""Property tests: the signed area of polygons and of loops with arcs against exact rationals
(research 01, Area and orientation)."""

import math
from fractions import Fraction

import pytest
from hypothesis import HealthCheck, assume, given, reject, settings
from hypothesis import strategies as st

import geometry2d_oracles as oracle
from geometry2d_checks import loop, polygon
from splintercam.foundation import Context
from splintercam.geometry2d import Arc, arc_from_bulge, signed_area

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


def _arc_bound(rows: list[list[float]]) -> float:
    """The rounding bound of the segment terms (DEC-G2D-016): 40u·r·length·min(1, φ²) per arc."""
    total = 0.0
    for x0, y0, _, _, cx, cy, sweep in rows:
        if sweep != 0.0:
            r = math.dist((x0, y0), (cx, cy))
            total += r * (r * abs(sweep)) * min(1.0, sweep * sweep)
    return 40 * U * total


def _check_area(ctx: Context, rows: list[list[float]]) -> None:
    """The result against the exact area: the sign whenever |A| clears eps_len·L by the bound,
    the value within the bound, and no value well below eps_len·L (DEC-G2D-016)."""
    exact = oracle.loop_area(rows)
    ends = [(row[0], row[1]) for row in rows]
    chords = sum(math.dist(p, q) for p, q in zip(ends, ends[1:] + ends[:1], strict=True))
    length = sum(
        math.dist(row[:2], row[2:4])
        if row[6] == 0.0
        else math.dist(row[:2], row[4:6]) * abs(row[6])
        for row in rows
    )
    xs, ys = [p[0] for p in ends], [p[1] for p in ends]
    e = max(max(xs) - min(xs), max(ys) - min(ys)) / 2
    largest = max(abs(v) for p in ends for v in p)
    translation = 2 * U * (e + U * largest) * chords
    polygon_sums = len(rows) * U * (math.sqrt(2) * e * chords + 3 * e * e) if e <= 3355.0 else 0.0
    # The final halving rounds once more: u·|A| with a margin for the comparison itself.
    bound = polygon_sums + translation + _arc_bound(rows) + 2 * U * abs(float(exact))
    eps_l = ctx.tolerances.length_eps_mm * length
    result = signed_area(loop(rows, ctx), ctx)
    if abs(exact) > eps_l + bound:
        assert result.value is not None
        assert (result.value > 0) == (exact > 0)
        assert abs(Fraction(result.value) - exact) <= Fraction(bound)
    elif abs(exact) < eps_l - bound:
        assert result.value is None


BULGES = st.one_of(st.none(), st.floats(-8.0, 8.0), st.floats(-1e-3, 1e-3))


@pytest.mark.req("REQ-G2D-001", "REQ-G2D-128", "REQ-G2D-130", "REQ-G2D-131", "REQ-G2D-132")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    offset=st.tuples(st.floats(-1e4, 1e4), st.floats(-1e4, 1e4)),
    half_extent=st.floats(1e-2, 2e4),  # both paths: the limit is 3355 mm
    edges=st.lists(st.tuples(GRID, GRID, BULGES), min_size=2, max_size=30),
)
def test_loops_with_arcs_keep_the_sign_and_the_bound(
    ctx: Context,
    offset: tuple[float, float],
    half_extent: float,
    edges: list[tuple[float, float, float | None]],
) -> None:
    points = [(offset[0] + half_extent * x, offset[1] + half_extent * y) for x, y, _ in edges]
    assume(all(oracle.in_safe_range(*p) for p in points))
    rows: list[list[float]] = []
    for (p, q), (_, _, bulge) in zip(
        zip(points, points[1:] + points[:1], strict=True), edges, strict=True
    ):
        curve = None if bulge is None or p == q else arc_from_bulge(p, q, bulge, ctx).value
        if isinstance(curve, Arc):
            assume(curve.p1 == q)  # not closed into a full circle by the nearly closed rule
            rows.append([*curve.p0, *curve.p1, *curve.centre, curve.sweep_rad])
        else:
            rows.append([*p, *q, math.nan, math.nan, 0.0])
    _check_area(ctx, rows)


@pytest.mark.req("REQ-G2D-128", "REQ-G2D-131")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    centre=st.tuples(st.floats(-1e4, 1e4), st.floats(-1e4, 1e4)),
    radius=st.floats(1e-3, 1e7),  # up to the precondition r·min(1, φ²) <= 10^7 mm
    angle=st.floats(0.0, math.tau),
    clockwise=st.booleans(),
)
def test_full_circles_up_to_the_radius_limit(
    ctx: Context, centre: tuple[float, float], radius: float, angle: float, clockwise: bool
) -> None:
    # One row, so the end points' box is a point and the float path takes every radius.
    p0 = (centre[0] + radius * math.cos(angle), centre[1] + radius * math.sin(angle))
    assume(all(oracle.in_safe_range(*p) for p in (p0, centre)))
    _check_area(ctx, [[*p0, *p0, *centre, -math.tau if clockwise else math.tau]])
