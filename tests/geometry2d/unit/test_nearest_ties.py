# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the kernel's tie candidates: every segment within eps of the nearest distance
(REQ-G2D-242; offset2d's class tie, REQ-OFF-034, DEC-OFF-001)."""

import math

import numpy as np
import pytest

from geometry2d_checks import nearest_ties
from splintercam import _kernels
from splintercam.geometry2d._distances import polyline_distances

# Segments 0 to 3: y = 0, x = 10, y = 10, x = 0 (each starts at the vertex of its index).
SQUARE = np.array([(0, 0), (10, 0), (10, 10), (0, 10)], dtype=np.float64)
STARTS = np.array([0], dtype=np.int64)


def _segments(q: tuple[float, float], limit: float, eps: float) -> list[int]:
    found = nearest_ties(np.array([q]), SQUARE, STARTS, limit, eps)
    assert (found[:, 0] == 0).all()
    return found[:, 1].tolist()


@pytest.mark.req("REQ-G2D-242")
def test_the_centre_of_a_square_ties_all_four_edges() -> None:
    assert _segments((5.0, 5.0), 6.0, 0.0) == [0, 1, 2, 3]


@pytest.mark.req("REQ-G2D-242")
def test_a_vertex_ties_the_two_edges_it_joins_at_distance_zero() -> None:
    assert _segments((0.0, 0.0), 1.0, 0.0) == [0, 3]
    assert _segments((10.0, 10.0), 1.0, 0.0) == [1, 2]


@pytest.mark.req("REQ-G2D-242")
def test_eps_widens_the_tie_inclusively() -> None:
    # Distances from (5, 1): 1 to edge 0, 5 to edges 1 and 3, 9 to edge 2.
    assert _segments((5.0, 1.0), 2.0, 0.0) == [0]
    assert _segments((5.0, 1.0), 2.0, 3.999) == [0]
    assert _segments((5.0, 1.0), 2.0, 4.0) == [0, 1, 3]  # 1 + 4 = 5 exactly: inside
    assert _segments((5.0, 1.0), 2.0, 8.0) == [0, 1, 2, 3]


@pytest.mark.req("REQ-G2D-242", "REQ-G2D-003")
def test_the_limit_bounds_the_nearest_distance_only() -> None:
    assert _segments((5.0, 1.0), 1.0, 4.0) == [0, 1, 3]  # nearest exactly at the limit
    assert _segments((5.0, 1.0), math.nextafter(1.0, 0.0), 4.0) == []
    assert _segments((5.0, 5.0), 4.9, 1.0) == []


@pytest.mark.req("REQ-G2D-242")
def test_rows_come_by_point_then_segment_across_several_loops() -> None:
    triangle = np.array([(20, 0), (30, 0), (20, 10)], dtype=np.float64)  # segments 4, 5, 6
    points = np.vstack([SQUARE, triangle])
    starts = np.array([0, 4], dtype=np.int64)
    q = np.array([(15.0, 5.0), (50.0, 50.0), (10.0, 0.0), (20.0, 0.0)])
    found = nearest_ties(q, points, starts, 6.0, 0.0)
    # (15, 5): edge 1 (x = 10) and edge 6 (x = 20) at 5; (50, 50): none; the corners: two each.
    assert found.tolist() == [[0, 1], [0, 6], [2, 0], [2, 1], [3, 4], [3, 6]]


@pytest.mark.req("REQ-G2D-242", "REQ-G2D-239")
def test_the_nearest_distance_is_that_of_polyline_distances() -> None:
    rng = np.random.default_rng(5)
    q = rng.uniform(-2.0, 12.0, size=(400, 2))
    found = nearest_ties(q, SQUARE, STARTS, 3.0, 0.0)
    distances = polyline_distances(q, SQUARE, STARTS, 3.0)
    assert sorted(set(found[:, 0].tolist())) == np.flatnonzero(np.isfinite(distances)).tolist()


@pytest.mark.req("REQ-G2D-242")
def test_a_short_output_is_filled_as_far_as_it_reaches() -> None:
    out = np.full((2, 2), -7, dtype=np.int64)
    q = np.array([(5.0, 5.0)])
    assert _kernels.geometry2d.nearest_ties(q, SQUARE, STARTS, 6.0, 0.0, out) == 4
    assert out.tolist() == [[0, 0], [0, 1]]


@pytest.mark.req("REQ-G2D-242")
def test_no_polylines_and_no_queries_give_no_rows() -> None:
    empty = np.empty((0, 2))
    assert nearest_ties(np.array([(1.0, 2.0)]), empty, np.empty(0, np.int64), 1.0, 0.0).size == 0
    assert nearest_ties(empty, SQUARE, STARTS, 1.0, 0.0).size == 0


@pytest.mark.req("REQ-G2D-242")
@pytest.mark.parametrize(
    ("limit", "eps", "word"),
    [
        (0.0, 0.0, "limit must"),
        (-1.0, 0.0, "limit must"),
        (math.inf, 0.0, "limit must"),
        (math.nan, 0.0, "limit must"),
        (1.0, -1e-9, "eps must"),
        (1.0, math.nan, "eps must"),
        (1.0, math.inf, "eps must"),
        (1e308, 1e308, "eps must"),  # limit + eps overflows
    ],
)
def test_a_bad_limit_or_eps_is_refused(limit: float, eps: float, word: str) -> None:
    with pytest.raises(ValueError, match=word):
        nearest_ties(np.array([(1.0, 2.0)]), SQUARE, STARTS, limit, eps)


@pytest.mark.req("REQ-G2D-242")
@pytest.mark.parametrize("starts", [[1], [0, 0], [0, 4]])
def test_broken_loop_starts_are_refused(starts: list[int]) -> None:
    with pytest.raises(ValueError, match="loop_starts"):
        nearest_ties(np.array([(1.0, 2.0)]), SQUARE, np.array(starts, np.int64), 1.0, 0.0)


@pytest.mark.req("REQ-G2D-242")
def test_a_non_finite_vertex_is_refused() -> None:
    square = SQUARE.copy()
    square[2, 0] = math.nan
    with pytest.raises(ValueError, match="finite"):
        nearest_ties(np.array([(1.0, 2.0)]), square, STARTS, 1.0, 0.0)


@pytest.mark.req("REQ-G2D-242")
def test_a_non_finite_query_point_is_refused() -> None:
    for bad in (math.nan, math.inf):
        with pytest.raises(ValueError, match="query point must be finite"):
            nearest_ties(np.array([(bad, 2.0)]), SQUARE, STARTS, 1.0, 0.0)


@pytest.mark.req("REQ-G2D-242")
def test_a_zero_length_segment_keeps_its_index_and_ties() -> None:
    # A repeated vertex makes segment 1 of length 0; segments are numbered as in
    # nearest_segments, so it keeps index 1 and ties like any other segment.
    points = np.array([(0.0, 0.0), (10.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    starts = np.array([0], dtype=np.int64)
    q = np.array([(10.0, 0.0), (12.0, 0.0)])
    found = nearest_ties(q, points, starts, 5.0, 0.0)
    assert found.tolist() == [[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2]]


@pytest.mark.req("REQ-G2D-242")
def test_the_grid_reaches_eps_beyond_a_small_limit() -> None:
    # Two parallel polylines of 0.05 mm segments, 1 mm apart, a query on the lower one: with
    # limit 0.02 and eps 1.5 the upper line's segments are candidates too, which a cell grid
    # sized for the limit alone (cells of about 0.05 mm) would not reach (spec review).
    xs = np.arange(0.0, 4.0001, 0.05)
    lower = [(float(x), 0.0) for x in xs]
    upper = [(float(x), 1.0) for x in xs[::-1]]
    points = np.array(lower + upper)
    starts = np.array([0], dtype=np.int64)
    found = nearest_ties(np.array([(2.0, 0.0)]), points, starts, 0.02, 1.5)
    segments = set(found[:, 1].tolist())
    assert any(s >= len(lower) for s in segments)  # the upper line's segments, at 1 mm
