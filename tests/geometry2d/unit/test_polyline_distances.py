# SPDX-License-Identifier: Apache-2.0
"""Unit tests for batched point-to-polyline distances (research 01, Loop tree, rules 3 and 5)."""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from splintercam.geometry2d._distances import polyline_distances

SQUARE = np.array([(0, 0), (10, 0), (10, 10), (0, 10)], dtype=np.float64)
STARTS = np.array([0], dtype=np.int64)


@pytest.mark.req("REQ-G2D-239")
def test_distances_within_the_limit_are_exact_and_beyond_it_infinite() -> None:
    q = np.array([(5.0, 0.5), (10.25, 5.0), (5.0, 5.0), (-0.3, -0.4), (5.0, 0.0), (0.1, 5.0)])
    out = polyline_distances(q, SQUARE, STARTS, 1.0)
    assert out[0] == 0.5
    assert out[1] == 0.25
    assert math.isinf(out[2])  # 5 mm from every edge, beyond the limit
    assert out[3] == pytest.approx(0.5, rel=0, abs=4 * math.ulp(0.5))  # to the corner
    assert out[4] == 0.0
    assert out[5] == 0.1  # the closing edge (0, 10) to (0, 0)


@pytest.mark.req("REQ-G2D-239")
def test_several_loops_and_long_edges() -> None:
    triangle = np.array([(-1000, -1000), (1000, -1000), (0, 1000)], dtype=np.float64)
    points = np.vstack([SQUARE, triangle])
    starts = np.array([0, 4], dtype=np.int64)
    q = np.array([(0.0, -999.9), (3.0, 3.0)])
    out = polyline_distances(q, points, starts, 0.2)
    assert out[0] == pytest.approx(0.1, rel=0, abs=4 * math.ulp(1000.0))
    assert math.isinf(out[1])


@pytest.mark.req("REQ-G2D-239")
def test_the_distance_does_not_depend_on_the_loop_direction() -> None:
    q = np.random.default_rng(7).uniform(-1, 11, size=(500, 2))
    forward = polyline_distances(q, SQUARE, STARTS, 3.0)
    backward = polyline_distances(q, SQUARE[::-1].copy(), STARTS, 3.0)
    assert forward.tobytes() == backward.tobytes()


@pytest.mark.req("REQ-G2D-239")
def test_an_empty_polyline_is_infinitely_far() -> None:
    out = polyline_distances(np.array([(1.0, 2.0)]), np.empty((0, 2)), np.empty(0, np.int64), 1.0)
    assert math.isinf(out[0])


@pytest.mark.req("REQ-G2D-239", "REQ-G2D-003")
def test_a_distance_exactly_at_the_limit_is_returned() -> None:
    out = polyline_distances(np.array([(5.0, 1.0)]), SQUARE, STARTS, 1.0)
    assert out[0] == 1.0


def _brute_force(q: NDArray[np.float64], points: NDArray[np.float64]) -> NDArray[np.float64]:
    a, b = points, np.roll(points, -1, axis=0)
    d = b - a
    t = np.clip(((q[:, None, :] - a) * d).sum(axis=2) / (d * d).sum(axis=1), 0.0, 1.0)
    foot = a + t[..., None] * d
    return np.hypot(*(q[:, None, :] - foot).transpose(2, 0, 1)).min(axis=1)


@pytest.mark.req("REQ-G2D-239")
def test_a_long_diagonal_edge_across_many_small_cells() -> None:
    # 4000 tiny segments of a small circle far away make the cells about 0.09 mm wide; the
    # triangle's diagonal from (0, 0) to (100, 100) then crosses about 1100 columns.
    angles = np.linspace(0.0, math.tau, 4000, endpoint=False)
    circle = np.column_stack([500.0 + np.cos(angles), 500.0 + np.sin(angles)])
    triangle = np.array([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)])
    points = np.vstack([triangle, circle])
    starts = np.array([0, 3], dtype=np.int64)
    rng = np.random.default_rng(11)
    along = rng.uniform(0.0, 100.0, 2000)
    offset = rng.uniform(-0.01, 0.01, 2000)
    q = np.column_stack([along - offset, along + offset])  # within 0.0142 mm of the diagonal
    out = polyline_distances(q, points, starts, 0.02)
    expected = _brute_force(q, triangle)
    np.testing.assert_allclose(out, expected, rtol=0, atol=4 * math.ulp(100.0))


@pytest.mark.req("REQ-G2D-239")
@pytest.mark.parametrize("limit", [0.0, -1.0, math.nan, math.inf])
def test_a_limit_that_is_not_positive_and_finite_is_refused(limit: float) -> None:
    with pytest.raises(ValueError, match="limit"):
        polyline_distances(np.array([(1.0, 2.0)]), SQUARE, STARTS, limit)


@pytest.mark.req("REQ-G2D-239")
@pytest.mark.parametrize("starts", [[1], [0, 0], [0, 4], [0, 3, 2]])
def test_broken_loop_starts_are_refused(starts: list[int]) -> None:
    with pytest.raises(ValueError, match="loop_starts"):
        polyline_distances(np.array([(1.0, 2.0)]), SQUARE, np.array(starts, np.int64), 1.0)


@pytest.mark.req("REQ-G2D-239")
def test_a_non_finite_vertex_is_refused() -> None:
    square = SQUARE.copy()
    square[2, 0] = math.nan
    with pytest.raises(ValueError, match="finite"):
        polyline_distances(np.array([(1.0, 2.0)]), square, STARTS, 1.0)


@pytest.mark.req("REQ-G2D-239")
def test_a_steep_edge_ending_beside_a_column_boundary_is_found() -> None:
    # Spec review, 2026-10-08: P.x - min x rounds up to the next column, whose boundary lies to the
    # right of P, so the edge was filed near Q only and a query 0.25 mm from it got +inf.
    p, q = (math.nextafter(0.7, 0.0), 0.0), (0.7, 10.0)
    left = [(-1.3, 10.0 - 0.5 * k) for k in range(21)]
    points = np.array(
        [p, q, (0.2, 10.0), (-0.3, 10.0), (-0.8, 10.0), *left, (-0.8, 0.0), (-0.3, 0.0), (0.2, 0.0)]
    )
    out = polyline_distances(np.array([(0.45, 2.0)]), points, STARTS, 0.5)
    assert out[0] == pytest.approx(0.25, rel=0, abs=4 * math.ulp(1.0))


@pytest.mark.req("REQ-G2D-239")
def test_points_without_loops_are_refused() -> None:
    with pytest.raises(ValueError, match="loop_starts"):
        polyline_distances(np.array([(1.0, 2.0)]), SQUARE, np.empty(0, np.int64), 1.0)


@pytest.mark.req("REQ-G2D-239")
def test_a_query_far_outside_the_grid_is_infinitely_far() -> None:
    out = polyline_distances(np.array([(1e300, 0.0), (-1e300, -1e300)]), SQUARE, STARTS, 1.0)
    assert np.isinf(out).all()
