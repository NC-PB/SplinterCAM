# SPDX-License-Identifier: Apache-2.0
"""Property tests: cleanup against exact rationals (research 01, Helpers)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

import geometry2d_oracles as oracle
from splintercam.foundation import Context
from splintercam.geometry2d import Line, cleanup, closest_point

# The ctx fixture holds a progress log and a debug sink that every example shares; cleanup uses
# neither, so sharing it is safe here.
shared_ctx = settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
grid = st.tuples(st.integers(-20, 20), st.integers(-20, 20)).map(
    lambda p: (float(p[0]), float(p[1]))
)


@pytest.mark.req("REQ-G2D-209", "REQ-G2D-211", "REQ-G2D-212")
@shared_ctx
@given(
    points=st.lists(grid, min_size=3, max_size=12, unique=True),
    spikes=st.lists(st.tuples(st.integers(0, 11), grid), max_size=4),
)
def test_spikes_leave_the_area_unchanged(
    ctx: Context, points: list[tuple[float, float]], spikes: list[tuple[int, tuple[float, float]]]
) -> None:
    # A spike from vertex a out to s and straight back to a has zero width.
    loop = list(points)
    for at, tip in sorted(spikes, reverse=True):
        a = loop[at % len(loop)]
        if tip != a:
            loop[at % len(loop) + 1 : at % len(loop) + 1] = [tip, a]
    result = cleanup(np.array(loop), ctx)
    assert result.value is not None
    indices: list[int] = result.value.tolist()
    kept = [loop[i] for i in indices]
    if len(kept) >= 3:
        assert oracle.polygon_area(kept) == oracle.polygon_area(loop)
    # What stays has no exactly collinear vertex between its neighbours and no spike.
    if len(kept) > 3:
        for prev, v, nxt in zip(kept[-1:] + kept[:-1], kept, kept[1:] + kept[:1], strict=True):
            assert oracle.orient2d(prev, nxt, v) != 0 or v in (prev, nxt)
    again = cleanup(np.array(kept), ctx)
    assert again.value is not None
    assert again.value.tolist() == list(range(len(kept)))
    assert again.diagnostics == ()


@pytest.mark.req("REQ-G2D-204", "REQ-G2D-206", "REQ-G2D-020")
@shared_ctx
@given(
    corners=st.lists(grid, min_size=3, max_size=10, unique=True),
    sizes=st.lists(st.integers(1, 3), min_size=10, max_size=10),
    jitter=st.lists(
        st.tuples(st.floats(-0.3, 0.3), st.floats(-0.3, 0.3)), min_size=30, max_size=30
    ),
)
def test_no_vertex_moves_by_more_than_eps_len(
    ctx: Context,
    corners: list[tuple[float, float]],
    sizes: list[int],
    jitter: list[tuple[float, float]],
) -> None:
    # Each corner becomes a cluster of up to three vertices within 0.43·eps_len of it.
    eps = ctx.tolerances.length_eps_mm
    loop: list[tuple[float, float]] = []
    for k, (corner, size) in enumerate(zip(corners, sizes, strict=False)):
        for j in range(size):
            dx, dy = jitter[3 * k + j]
            loop.append((corner[0] + dx * eps, corner[1] + dy * eps))
    assume(len(loop) >= 3)
    result = cleanup(np.array(loop), ctx)
    assert result.value is not None
    indices: list[int] = result.value.tolist()
    kept = [loop[i] for i in indices]
    # Every vertex lies within eps_len of a kept one (merged) or of the kept loop's edges (a
    # collinear vertex dropped); a dropped spike tip moves nowhere, it goes with its spike.
    tips = {int(d.location.split()[-1]) for d in result.diagnostics if d.location is not None}
    edges = [Line(a, b) for a, b in zip(kept, kept[1:] + kept[:1], strict=True)]
    for i, p in enumerate(loop):
        if i in tips:
            continue
        near_vertex = min(math.dist(p, q) for q in kept) <= eps
        assert near_vertex or min(closest_point(e, p, ctx).distance_mm for e in edges) <= eps
