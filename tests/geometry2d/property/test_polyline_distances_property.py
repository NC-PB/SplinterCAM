# SPDX-License-Identifier: Apache-2.0
"""Property test: the batched distances equal a brute-force oracle (research 01, Loop tree)."""

import math

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from splintercam.geometry2d._distances import polyline_distances


def _oracle(q: NDArray[np.float64], points: NDArray[np.float64]) -> NDArray[np.float64]:
    """Distance to the nearest segment of one closed polyline, from both ends (DEC-G2D-013)."""
    a, b = points, np.roll(points, -1, axis=0)
    best = np.full(q.shape[0], np.inf)
    for start, end in ((a, b), (b, a)):
        d = end - start
        length2 = (d * d).sum(axis=1)
        along = ((q[:, None, :] - start) * d).sum(axis=2)
        safe = np.where(length2 > 0.0, length2, 1.0)  # a zero-length segment: its start, t = 0
        t = np.clip(np.where(length2 > 0.0, along / safe, 0.0), 0.0, 1.0)
        foot = start + t[..., None] * d
        best = np.minimum(best, np.hypot(*(q[:, None, :] - foot).transpose(2, 0, 1)).min(axis=1))
    return best


coordinates = st.floats(-50.0, 50.0).map(lambda v: round(v * 2**20) / 2**20)  # DEC-G2D-015


@pytest.mark.req("REQ-G2D-239", "REQ-G2D-003")
@settings(deadline=None)
@given(
    loops=st.lists(
        st.lists(st.tuples(coordinates, coordinates), min_size=3, max_size=20, unique=True),
        min_size=1,
        max_size=3,
    ),
    queries=st.lists(st.tuples(coordinates, coordinates), min_size=1, max_size=40),
    limit=st.floats(1e-4, 30.0),
)
def test_distances_equal_brute_force_within_the_limit(
    loops: list[list[tuple[float, float]]], queries: list[tuple[float, float]], limit: float
) -> None:
    polylines = [np.array(one, dtype=np.float64) for one in loops]
    points = np.vstack(polylines)
    starts = np.cumsum([0] + [len(one) for one in loops[:-1]], dtype=np.int64)
    q = np.array(queries, dtype=np.float64)
    out = polyline_distances(q, points, starts, limit)
    expected = np.min([_oracle(q, one) for one in polylines], axis=0)
    # Same formula; NumPy's hypot and the oracle's foot a + 1·d may each round once more, a unit
    # of the coordinates (|v| <= 100 here).
    slack = 4 * math.ulp(100.0)
    near = expected <= limit - slack
    np.testing.assert_allclose(out[near], expected[near], rtol=0, atol=slack)
    assert (out[expected > limit + slack] == math.inf).all()
    assert all(math.isinf(v) or v <= limit for v in out.tolist())  # REQ-G2D-003


@st.composite
def _steep_loops(draw: st.DrawFn) -> NDArray[np.float64]:
    """A loop whose vertices sit within a few rounding units of multiples of 1/4 in x, so edges
    are nearly vertical and end beside column boundaries, moved by up to 10^6 mm."""
    n = draw(st.integers(3, 30))
    offset = draw(st.sampled_from([0.0, 1e3, 1e6]))
    vertices: list[tuple[float, float]] = []
    for _ in range(n):
        x = offset + draw(st.integers(-8, 8)) / 4
        for _ in range(draw(st.integers(0, 3))):
            x = math.nextafter(x, draw(st.sampled_from([math.inf, -math.inf])))
        vertices.append((x, offset + draw(st.floats(-5.0, 5.0))))
    return np.array(vertices, dtype=np.float64)


@pytest.mark.req("REQ-G2D-239")
@settings(deadline=None)
@given(
    points=_steep_loops(),
    queries=st.lists(
        st.tuples(st.floats(-2.5, 2.5), st.floats(-5.0, 5.0)), min_size=1, max_size=30
    ),
    limit=st.sampled_from([0.1, 0.125, 0.25, 0.5, 1.0]),
)
def test_steep_edges_beside_column_boundaries(
    points: NDArray[np.float64], queries: list[tuple[float, float]], limit: float
) -> None:
    first_y = float(points[0, 1])
    offset = round(first_y / 1e3) * 1e3 if abs(first_y) > 100 else 0.0  # the drawn offset
    q = np.array(queries, dtype=np.float64) + offset
    out = polyline_distances(q, points, np.zeros(1, np.int64), limit)
    expected = _oracle(q, points)
    slack = 8 * math.ulp(abs(offset) + 10.0)  # rounding of coordinates near the offset
    near = expected <= limit - slack
    np.testing.assert_allclose(out[near], expected[near], rtol=0, atol=slack)
    assert (out[expected > limit + slack] == math.inf).all()
