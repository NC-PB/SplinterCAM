# SPDX-License-Identifier: Apache-2.0
"""Property test: a side-correct flattened region lies in air within t (research 01, Flattening,
test 16)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from geometry2d_checks import nested_tree
from splintercam.foundation import Context
from splintercam.geometry2d import (
    Arc,
    PointLocation,
    RegionKind,
    arc_from_bulge,
    flatten_loops,
    point_in_region,
    polygon_region,
)

NAN = math.nan
R_OUTER = 20.0  # outer vertices on this circle, gaps of at most π/2: every edge ≥ 14 mm from 0
MAX_BULGE = 0.3  # sagitta ≤ 0.15 chord ≤ 4.3 mm, so inward arcs keep clear of the island


def _row(
    p0: tuple[float, float], p1: tuple[float, float], bulge: float, ctx: Context
) -> list[float]:
    built = arc_from_bulge(p0, p1, bulge, ctx)
    assert built.value is not None, built.diagnostics
    curve = built.value
    if isinstance(curve, Arc):
        return [*p0, *p1, *curve.centre, curve.sweep_rad]
    return [*p0, *p1, NAN, NAN, 0.0]


@st.composite
def _regions(draw: st.DrawFn) -> tuple[list[list[float]], list[list[float]]]:
    """A CCW outer loop of lines and arcs (bulges) around a CW island circle about the origin."""
    n = draw(st.integers(6, 12))
    step = math.tau / n  # with jitter below 0.2 steps, every gap stays under π/2
    jitter = draw(st.lists(st.floats(-0.2, 0.2), min_size=n, max_size=n))
    angles = [(k + j) * step for k, j in enumerate(jitter)]
    points = [(R_OUTER * math.cos(a), R_OUTER * math.sin(a)) for a in angles]
    bulges = draw(st.lists(st.floats(-MAX_BULGE, MAX_BULGE), min_size=n, max_size=n))
    outer = [
        [*p0, *p1, bulge]
        for p0, p1, bulge in zip(points, points[1:] + points[:1], bulges, strict=True)
    ]
    radius = draw(st.floats(0.5, 8.0))
    if draw(st.booleans()):  # two CW half circles
        island = [
            [radius, 0.0, -radius, 0.0, 0.0, 0.0, -math.pi],
            [-radius, 0.0, radius, 0.0, 0.0, 0.0, -math.pi],
        ]
    else:
        island = [[radius, 0.0, radius, 0.0, 0.0, 0.0, -math.tau]]
    return outer, island


def _distances(q: NDArray[np.float64], rows: NDArray[np.float64]) -> NDArray[np.float64]:
    """Distance of each point of q to the nearest curve row (test oracle, NumPy)."""
    best = np.full(q.shape[0], np.inf)
    values: list[list[float]] = rows.tolist()
    for x0, y0, x1, y1, cx, cy, sweep in values:
        if sweep == 0.0:
            a, d = np.array([x0, y0]), np.array([x1 - x0, y1 - y0])
            t = np.clip(((q - a) @ d) / (d @ d), 0.0, 1.0)
            foot = q - a - t[:, None] * d
            dist: NDArray[np.float64] = np.hypot(foot[:, 0], foot[:, 1])
        else:
            r = math.hypot(x0 - cx, y0 - cy)
            start = math.atan2(y0 - cy, x0 - cx)
            angle = np.arctan2(q[:, 1] - cy, q[:, 0] - cx) - start
            along = np.mod(angle * math.copysign(1.0, sweep), math.tau)
            inside = along <= abs(sweep)
            ends = np.minimum(
                np.hypot(q[:, 0] - x0, q[:, 1] - y0), np.hypot(q[:, 0] - x1, q[:, 1] - y1)
            )
            on_circle = np.abs(np.hypot(q[:, 0] - cx, q[:, 1] - cy) - r)
            dist = np.where(inside, on_circle, ends)
        best = np.minimum(best, dist)
    return best


# The ctx fixture holds a progress log and a debug sink that every example shares; flatten_loops
# uses neither, so sharing it is safe here.
@pytest.mark.req("REQ-G2D-115", "REQ-G2D-116", "REQ-G2D-119", "REQ-G2D-184", "REQ-G2D-199")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(region=_regions(), kind=st.sampled_from([RegionKind.MATERIAL, RegionKind.AIR]))
def test_flattened_region_lies_in_air_within_t(
    ctx: Context, region: tuple[list[list[float]], list[list[float]]], kind: RegionKind
) -> None:
    drawn, island = region
    outer = [_row((r[0], r[1]), (r[2], r[3]), r[4], ctx) for r in drawn]
    tree = nested_tree([outer, island], ctx)
    flat = flatten_loops(tree, kind, ctx).region
    checked = polygon_region(flat.points, flat.loop_starts, flat.source_ids, flat.fixed, ctx)
    assert checked.ok, checked.diagnostics

    ends = np.append(flat.loop_starts[1:], flat.points.shape[0])
    samples: list[NDArray[np.float64]] = []
    for start, end in zip(flat.loop_starts, ends, strict=True):
        loop = flat.points[start:end]
        # Samples at 0, 1/4, 1/2 and 3/4 of each segment. An inscribed chord deviates most from
        # its circle at its middle, a circumscribed segment at its vertices (s = 0, and each P1 is
        # s = 0 of the next row); a segment on the wrong side is wrong all along. The nearest row
        # is the segment's own: outer arcs and the island stay at least 1.9 mm apart.
        s = np.linspace(0.0, 1.0, 4, endpoint=False)[:, None, None]
        samples.append((loop + s * (np.roll(loop, -1, axis=0) - loop)).reshape(-1, 2))
    q = np.vstack(samples)

    locations = point_in_region(q, tree.loops, ctx)
    wrong_side = PointLocation.IN if kind is RegionKind.MATERIAL else PointLocation.OUT
    assert not (locations == wrong_side).any()  # in air or on the true boundary

    t_flat = ctx.tolerances.flatten_tol_mm
    # REQ-G2D-110's allowance, taken over all arcs: 4 rounding units of r, and P1's distance from
    # its circle. No arc here is reversed, so REQ-G2D-119's eps_len does not apply.
    rows = tree.loops.rows
    arcs = rows[rows[:, 6] != 0.0]
    radius = np.hypot(arcs[:, 0] - arcs[:, 4], arcs[:, 1] - arcs[:, 5])
    p1_off = np.abs(np.hypot(arcs[:, 2] - arcs[:, 4], arcs[:, 3] - arcs[:, 5]) - radius)
    slack = 4 * math.ulp(float(radius.max())) + float(p1_off.max())
    assert _distances(q, rows).max() <= t_flat + slack
