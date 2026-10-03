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


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139", "REQ-G2D-143", "REQ-G2D-149", "REQ-G2D-150")
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


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-139", "REQ-G2D-149")
@shared_ctx
@given(
    corners=st.lists(
        st.tuples(st.floats(-10.0, 10.0), st.floats(-10.0, 10.0)), min_size=2, max_size=6
    ),
    bulges=st.lists(st.floats(-2.0, 2.0), min_size=6, max_size=6),
    queries=st.lists(
        st.tuples(st.floats(-25.0, 25.0), st.floats(-25.0, 25.0)), min_size=1, max_size=30
    ),
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


@pytest.mark.req("REQ-G2D-148")
@shared_ctx
@given(
    bulges=st.lists(st.floats(-2.0, 2.0), min_size=4, max_size=4),
    along=st.floats(0.0, 1.0),
    edge=st.integers(0, 3),
    offset=st.sampled_from([0.0, 2.0**-30, 0.5e-6, 0.99e-6, 1.01e-6, 2e-6, 1e-3]),
    direction=st.floats(0.0, math.tau),
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
    distance = min(closest_point(c, q, ctx).distance_mm for c in curves)
    found = PointLocation(point_in_region(np.array([q]), loops, ctx)[0])
    exact = PointLocation(point_in_region_exact(np.array([q]), loops)[0])
    if distance <= eps * (1 - 1e-9):
        assert found is ON
    elif distance > eps * (1 + 1e-9):
        assert found is exact
        assert found is not ON
