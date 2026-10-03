# SPDX-License-Identifier: Apache-2.0
"""Property tests: point in region against an exact winding oracle, against a fine flattening and
against the distances of closest_point (research 01, Point in region)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

import geometry2d_oracles as oracle
from geometry2d_checks import polygon
from splintercam.foundation import Context
from splintercam.geometry2d import (
    Arc,
    Curve,
    CurveRows,
    Line,
    PointLocation,
    arc_from_bulge,
    closest_point,
    curve_rows,
    flatten,
    point_in_region,
)
from splintercam.geometry2d._region import point_in_region_exact

IN, OUT, ON = PointLocation.IN, PointLocation.OUT, PointLocation.ON
# The ctx fixture holds a progress log and a debug sink that every example shares; these
# functions use neither, so sharing it is safe here.
shared_ctx = settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
# Small integer grids, so rays meet vertices and points fall on edges often.
grid_point = st.tuples(st.integers(-6, 6), st.integers(-6, 6)).map(lambda p: (p[0] / 2, p[1] / 2))
# Coordinates on a 2^-20 mm grid within ±16 mm: no values below the predicates' input range.
FINE = st.integers(-(2**24), 2**24).map(lambda k: k / 2**20)
fine_point = st.tuples(FINE, FINE)


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139", "REQ-G2D-143")
@shared_ctx
@given(
    points=st.lists(grid_point, min_size=3, max_size=12),
    queries=st.lists(grid_point, min_size=1, max_size=20),
)
def test_polygons_match_the_exact_winding_oracle(
    ctx: Context, points: list[tuple[float, float]], queries: list[tuple[float, float]]
) -> None:
    assume(all(p != q for p, q in zip(points, points[1:] + points[:1], strict=True)))
    expected: list[PointLocation] = []
    for q in queries:
        w = oracle.winding(q, points)
        expected.append(ON if w is None else IN if w != 0 else OUT)
    for loop_points in (points, points[::-1]):
        found = point_in_region_exact(np.array(queries), polygon(loop_points, ctx))
        assert [PointLocation(v) for v in found] == expected


def _bulged_loop(
    points: list[tuple[float, float]], bulges: list[float], ctx: Context
) -> list[Curve]:
    curves: list[Curve] = []
    for p, q, b in zip(points, points[1:] + points[:1], bulges, strict=True):
        made = arc_from_bulge(p, q, b, ctx).value
        assert made is not None
        curves.append(made)
    return curves


def _rows(curves: list[Curve], ctx: Context) -> CurveRows:
    rows = [
        [*c.p0, *c.p1, *c.centre, c.sweep_rad]
        if isinstance(c, Arc)
        else [*c.p0, *c.p1, math.nan, math.nan, 0.0]
        for c in curves
    ]
    built = curve_rows(np.array(rows), np.arange(len(rows)), np.zeros(1, np.int64), ctx)
    assert built.value is not None, built.diagnostics
    return built.value


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139")
@shared_ctx
@given(
    corners=st.lists(fine_point, min_size=2, max_size=6),
    bulges=st.lists(st.floats(-2.0, 2.0), min_size=6, max_size=6),
    queries=st.lists(fine_point, min_size=1, max_size=30),
)
def test_arcs_match_a_fine_flattening_away_from_the_boundary(
    ctx: Context,
    corners: list[tuple[float, float]],
    bulges: list[float],
    queries: list[tuple[float, float]],
) -> None:
    pairs = zip(corners, corners[1:] + corners[:1], strict=True)
    assume(all(math.dist(p, q) > 0.1 for p, q in pairs))
    curves = _bulged_loop(corners, bulges[: len(corners)], ctx)
    # Every point of the flattening within 1e-5 mm of its curve, inscribed.
    flat = [(float(p[0]), float(p[1])) for c in curves for p in flatten(c, 1e-5, None, ctx)[:-1]]
    far = [q for q in queries if min(closest_point(c, q, ctx).distance_mm for c in curves) > 1e-3]
    assume(far)
    exact = point_in_region_exact(np.array(far), _rows(curves, ctx))
    flattened = point_in_region_exact(np.array(far), polygon(flat, ctx))
    assert exact.tolist() == flattened.tolist()


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139")
@shared_ctx
@given(
    start=st.floats(-math.pi, math.pi),
    sweep=st.floats(0.05, 6.2).flatmap(lambda s: st.sampled_from([s, -s])),
    radial=st.floats(-0.9e-6, 0.9e-6),
    queries=st.lists(fine_point, min_size=1, max_size=30),
)
def test_p1_off_the_circle_matches_arc_and_connector_flattened(
    ctx: Context,
    start: float,
    sweep: float,
    radial: float,
    queries: list[tuple[float, float]],
) -> None:
    # An arc of radius 10 about the origin whose P1 lies `radial` off the circle, closed by its
    # chord: the exact layer against the flattened arc to P1's ray, the radial connector to P1
    # and the chord (Peter, 2026-10-03), at points farther than 1e-3 mm from all of them.
    r = 10.0
    p0 = (r * math.cos(start), r * math.sin(start))
    end = start + sweep
    p1 = ((r + radial) * math.cos(end), (r + radial) * math.sin(end))
    on_circle = (r * math.cos(end), r * math.sin(end))
    rows = [[*p0, *p1, 0.0, 0.0, sweep], [*p1, *p0, math.nan, math.nan, 0.0]]
    built = curve_rows(np.array(rows), np.arange(2), np.zeros(1, np.int64), ctx)
    assume(built.value is not None)
    assert built.value is not None
    arc = Arc(p0, on_circle, (0.0, 0.0), sweep)
    flat = [(float(p[0]), float(p[1])) for p in flatten(arc, 1e-6, None, ctx)[:-1]]
    flat += [on_circle, p1]
    boundary = [arc, Line(on_circle, p1), Line(p1, p0)]
    far = [q for q in queries if min(closest_point(c, q, ctx).distance_mm for c in boundary) > 1e-3]
    assume(far)
    exact = point_in_region_exact(np.array(far), built.value)
    flattened = point_in_region_exact(np.array(far), polygon(flat, ctx))
    assert exact.tolist() == flattened.tolist()


@pytest.mark.req("REQ-G2D-148", "REQ-G2D-149", "REQ-G2D-150")
@shared_ctx
@given(
    bulges=st.lists(st.floats(-2.0, 2.0), min_size=4, max_size=4),
    along=st.floats(0.0, 1.0),
    edge=st.integers(0, 3),
    offset=st.sampled_from([0.0, 2.0**-30, 0.5e-6, 0.99e-6, 1.01e-6, 2e-6, 1e-3]),
    # On a grid of 2^20 directions: no tiny sines below the predicates' input range.
    direction=st.integers(0, 2**20).map(lambda k: k * math.tau / 2**20),
)
def test_the_tolerance_layer_is_on_within_eps_len(  # noqa: PLR0913 (Hypothesis draws)
    ctx: Context,
    bulges: list[float],
    along: float,
    edge: int,
    offset: float,
    direction: float,
) -> None:
    corners = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    curves = _bulged_loop(corners, bulges, ctx)
    # A point near the chosen edge: a flattened point moved by `offset` in some direction.
    flat = flatten(curves[edge], 1e-9, None, ctx)
    base = flat[min(int(along * (len(flat) - 1)), len(flat) - 1)]
    q = (
        float(base[0]) + offset * math.cos(direction),
        float(base[1]) + offset * math.sin(direction),
    )
    loops = _rows(curves, ctx)
    eps = ctx.tolerances.length_eps_mm
    # REQ-G2D-148 as amended: an arc is measured to the nearer of its radii |P0 - C| and |P1 - C|,
    # and the reversed arc has the second. The band absorbs a point equally near both ends.
    reversed_curves = [
        Arc(c.p1, c.p0, c.centre, -c.sweep_rad) if isinstance(c, Arc) else Line(c.p1, c.p0)
        for c in curves[::-1]
    ]
    distance = min(closest_point(c, q, ctx).distance_mm for c in curves + reversed_curves)
    found = PointLocation(point_in_region(np.array([q]), loops, ctx)[0])
    assert point_in_region(np.array([q]), _rows(reversed_curves, ctx), ctx)[0] == found
    exact = PointLocation(point_in_region_exact(np.array([q]), loops)[0])
    if distance <= eps * (1 - 1e-9):
        assert found is ON
    elif distance > eps * (1 + 1e-9):
        assert found is exact
        assert found is not ON


@pytest.mark.req("REQ-G2D-150")
@shared_ctx
@given(
    r0=st.floats(2e-6, 1e-3),
    radial=st.floats(-1e-6, 1e-6),
    behind=st.floats(0.0, 1.0),
    sweep=st.floats(1e-9, 1e-3),
    samples=st.lists(st.tuples(st.floats(0.0, 1.0), st.floats(0.0, 1.0)), min_size=1, max_size=20),
)
def test_both_orientations_agree_for_a_short_arc_with_p1_behind_and_off(  # noqa: PLR0913
    ctx: Context,
    r0: float,
    radial: float,
    behind: float,
    sweep: float,
    samples: list[tuple[float, float]],
) -> None:
    # Spec review of step 8b: a short arc whose P1 lies both off the circle (REQ-G2D-042) and
    # just behind P0 (REQ-G2D-043) draws the wedge between P1's and P0's rays on |P0 - C| one
    # way and on |P1 - C| the other. Where both orientations are valid input, points in the band
    # between the radii must get one answer.
    r1 = r0 + radial
    over = behind * ctx.tolerances.length_eps_mm / max(r0, r1)
    p0, p1 = (r0, 0.0), (r1 * math.cos(-over), r1 * math.sin(-over))
    tail = [(p1[0], -1.0), (-1.0, -1.0), (-1.0, 0.0)]
    corners = [p1, *tail, p0]
    rows = [[*p0, *p1, 0.0, 0.0, sweep]] + [
        [*a, *b, math.nan, math.nan, 0.0] for a, b in zip(corners, corners[1:], strict=False)
    ]
    reversed_rows = [[x1, y1, x0, y0, cx, cy, -s] for x0, y0, x1, y1, cx, cy, s in rows[::-1]]
    built = [
        curve_rows(np.array(r), np.arange(len(r)), np.zeros(1, np.int64), ctx).value
        for r in (rows, reversed_rows)
    ]
    assume(built[0] is not None and built[1] is not None)
    forward, backward = built
    assert forward is not None and backward is not None
    low, high = min(r0, r1), max(r0, r1)
    q = np.array(
        [
            (
                (low + u * (high - low)) * math.cos(-v * over),
                (low + u * (high - low)) * math.sin(-v * over),
            )
            for u, v in samples
        ]
    )
    assert point_in_region(q, forward, ctx).tolist() == point_in_region(q, backward, ctx).tolist()


@pytest.mark.req("REQ-G2D-150")
@shared_ctx
@given(
    angle=st.integers(1, 2**20 - 1).map(lambda k: k * (math.pi / 2) / 2**20),
    along=st.floats(0.05, 0.95),
    offset=st.floats(0.9e-6, 1.1e-6),
    inward=st.booleans(),
)
def test_both_orientations_agree_next_to_a_slanted_edge(
    ctx: Context, angle: float, along: float, offset: float, inward: bool
) -> None:
    # A square of side 10 turned by `angle`: the foot a + t·(b - a) and b + t'·(a - b) round
    # differently on a slanted edge, so a point about eps_len from it must not depend on which
    # end the edge starts at (spec review of step 8b).
    c, s = math.cos(angle), math.sin(angle)
    corners = [
        (10 * (c * x - s * y), 10 * (s * x + c * y)) for x, y in [(0, 0), (1, 0), (1, 1), (0, 1)]
    ]
    (ax, ay), (bx, by) = corners[0], corners[1]
    normal = (s, -c) if not inward else (-s, c)  # (s, -c) points out of the square
    q = np.array(
        [[ax + along * (bx - ax) + offset * normal[0], ay + along * (by - ay) + offset * normal[1]]]
    )
    forward = point_in_region(q, polygon(corners, ctx), ctx)
    backward = point_in_region(q, polygon(corners[::-1], ctx), ctx)
    assert forward.tolist() == backward.tolist()
