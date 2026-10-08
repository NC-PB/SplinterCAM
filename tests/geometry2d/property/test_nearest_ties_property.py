# SPDX-License-Identifier: Apache-2.0
"""Property tests: the kernel's tie candidates equal a brute-force O(n·m) oracle, bit for bit
(REQ-G2D-242), on random loops and on mirrored loops whose ties are exact by construction."""

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from geometry2d_checks import nearest_ties
from splintercam.geometry2d._distances import polyline_distances

Loops = list[list[tuple[float, float]]]


def _from_start(
    q: NDArray[np.float64], start: NDArray[np.float64], end: NDArray[np.float64]
) -> NDArray[np.float64]:
    """(n, m) distances from q to segments start → end, with the kernel's operations in its
    order (DEC-G2D-013; the build contracts nothing, REQ-G2D-014), so equal bit for bit."""
    dx, dy = end[:, 0] - start[:, 0], end[:, 1] - start[:, 1]
    length2 = dx * dx + dy * dy
    ux, uy = q[:, None, 0] - start[None, :, 0], q[:, None, 1] - start[None, :, 1]
    safe = np.where(length2 > 0.0, length2, 1.0)
    t = np.where(length2 > 0.0, np.clip((ux * dx + uy * dy) / safe, 0.0, 1.0), 0.0)
    fx = np.where(t == 0.0, start[:, 0], np.where(t == 1.0, end[:, 0], start[:, 0] + t * dx))
    fy = np.where(t == 0.0, start[:, 1], np.where(t == 1.0, end[:, 1], start[:, 1] + t * dy))
    ex, ey = q[:, None, 0] - fx, q[:, None, 1] - fy
    return np.sqrt(ex * ex + ey * ey)  # correctly rounded, like the kernel's length()


def _oracle(
    q: NDArray[np.float64], loops: Loops, limit: float, eps: float
) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    """Every (point, segment) with d <= d_min + eps where d_min <= limit, by brute force, and
    d_min per point."""
    a = np.vstack([np.array(one, dtype=np.float64) for one in loops])
    b = np.vstack([np.roll(np.array(one, dtype=np.float64), -1, axis=0) for one in loops])
    d = np.minimum(_from_start(q, a, b), _from_start(q, b, a))
    nearest = d.min(axis=1)
    within = (d <= (nearest + eps)[:, None]) & (nearest <= limit)[:, None]
    return np.argwhere(within).astype(np.int64), nearest  # by point, then segment


def _check(q: NDArray[np.float64], loops: Loops, limit: float, eps: float) -> NDArray[np.int64]:
    points = np.vstack([np.array(one, dtype=np.float64) for one in loops])
    starts = np.cumsum([0] + [len(one) for one in loops[:-1]], dtype=np.int64)
    found = nearest_ties(q, points, starts, limit, eps)
    expected, nearest = _oracle(q, loops, limit, eps)
    assert found.tolist() == expected.tolist()
    # The nearest distance is polyline_distances', bit for bit (REQ-G2D-239).
    distances = polyline_distances(q, points, starts, limit)
    assert sorted(set(found[:, 0].tolist())) == np.flatnonzero(np.isfinite(distances)).tolist()
    assert np.array_equal(np.where(nearest <= limit, nearest, np.inf), distances)
    return found


coordinates = st.floats(-50.0, 50.0).map(lambda v: round(v * 2**20) / 2**20)  # DEC-G2D-015
loop_lists = st.lists(
    st.lists(st.tuples(coordinates, coordinates), min_size=3, max_size=20, unique=True),
    min_size=1,
    max_size=3,
)
eps_values = st.one_of(st.sampled_from([0.0, 1e-6, 2.0**-20, 1e-3]), st.floats(0.0, 5.0))


@pytest.mark.req("REQ-G2D-242", "REQ-G2D-003")
@settings(deadline=None)
@given(
    loops=loop_lists,
    queries=st.lists(st.tuples(coordinates, coordinates), min_size=1, max_size=30),
    limit=st.floats(1e-4, 30.0),
    eps=eps_values,
)
def test_ties_equal_brute_force_with_vertices_as_queries(
    loops: Loops, queries: list[tuple[float, float]], limit: float, eps: float
) -> None:
    # A vertex lies at distance 0 from both segments it joins: an exact tie.
    vertices = [p for one in loops for p in one]
    q = np.array(queries + vertices, dtype=np.float64)
    found = _check(q, loops, limit, eps)
    first = len(queries)
    assert all(np.count_nonzero(found[:, 0] == first + k) >= 2 for k in range(len(vertices)))


@pytest.mark.req("REQ-G2D-242")
@settings(deadline=None)
@given(
    loops=loop_lists,
    heights=st.lists(coordinates, min_size=1, max_size=30),
    limit=st.floats(1e-4, 100.0),
    eps=eps_values,
)
def test_mirrored_loops_tie_on_the_mirror_line(
    loops: Loops, heights: list[float], limit: float, eps: float
) -> None:
    # Each loop and its mirror image in x = 0: x -> -x negates every difference and product
    # exactly, so a point on x = 0 is at the same distance from a segment and its image.
    mirrored = [[(-x, y) for x, y in one] for one in loops]
    q = np.array([(0.0, y) for y in heights], dtype=np.float64)
    found = _check(q, loops + mirrored, limit, eps)
    assume(found.size > 0)  # a mirror line beyond the limit ties nothing
    half = sum(len(one) for one in loops)
    pairs = {(int(p), int(s)) for p, s in found}
    assert pairs == {(p, (s + half) % (2 * half)) for p, s in pairs}


@pytest.mark.req("REQ-G2D-242")
@settings(deadline=None)
@given(
    sides=st.integers(200, 600),
    radius=st.floats(5.0, 15.0).map(lambda v: round(v * 2**20) / 2**20),
    queries=st.lists(
        st.tuples(st.floats(-20.0, 20.0), st.floats(-20.0, 20.0)), min_size=1, max_size=30
    ),
    limit=st.floats(0.5, 3.0),
    eps=st.one_of(st.sampled_from([0.0, 1e-6]), st.floats(0.0, 2.0)),
)
def test_ties_on_a_fine_mesh_reach_across_cells(
    sides: int, radius: float, queries: list[tuple[float, float]], limit: float, eps: float
) -> None:
    # Segments of about 0.1 mm against a limit + eps of a few mm: the cell side comes from
    # limit + eps, not the mean segment length, so candidates lie near cell edges and the
    # two-cell reach of the search is what finds them (spec review, 2026-10-08).
    angles = np.arange(sides) * (2.0 * np.pi / sides)
    ring = np.round(np.column_stack((np.cos(angles), np.sin(angles))) * radius * 2**20) / 2**20
    loop = [(float(x), float(y)) for x, y in ring]
    assume(len(set(loop)) == len(loop))  # no vertex repeated by the rounding
    q = np.array(queries, dtype=np.float64)
    _check(q, [loop], limit, eps)
