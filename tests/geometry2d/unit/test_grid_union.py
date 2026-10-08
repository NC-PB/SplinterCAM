# SPDX-License-Identifier: Apache-2.0
"""Unit and randomised tests of the grid bridge (research 01, Tolerances, resolution chain;
test 21)."""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes
from splintercam.foundation import TOLERANCE_DEFAULTS, Context
from splintercam.geometry2d import CurveRows, PointLocation, _grid, point_in_region
from splintercam.geometry2d._distances import polyline_distances
from splintercam.geometry2d._grid import grid_union


def _box(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _layout(
    loops: list[list[tuple[float, float]]],
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    points = np.array([p for loop in loops for p in loop], dtype=np.float64)
    starts = np.cumsum([0] + [len(loop) for loop in loops[:-1]], dtype=np.int64)
    return points, starts


def _rows(points: NDArray[np.float64], starts: NDArray[np.int64]) -> CurveRows:
    ends = np.append(starts[1:], points.shape[0])
    rows: list[list[float]] = []
    for a, b in zip(starts.tolist(), ends.tolist(), strict=True):
        loop: list[list[float]] = points[a:b].tolist()
        for p, q in zip(loop, loop[1:] + loop[:1], strict=True):
            rows.append([*p, *q, math.nan, math.nan, 0.0])
    return CurveRows(np.array(rows), np.arange(len(rows), dtype=np.int64), starts)


def _random_loops(rng: np.random.Generator, ctx: Context) -> list[list[tuple[float, float]]]:
    """Squares and many-sided polygons, some pairs closer than t_topo (test 21)."""
    t_topo = ctx.tolerances.topology_tol_mm
    loops: list[list[tuple[float, float]]] = []
    for _ in range(int(rng.integers(2, 6))):
        cx, cy, r = rng.uniform(0, 40), rng.uniform(0, 40), rng.uniform(1, 8)
        n = int(rng.integers(3, 40))
        angles = np.sort(rng.uniform(0, math.tau, n))
        loops.append([(cx + r * math.cos(a), cy + r * math.sin(a)) for a in angles.tolist()])
    x0 = float(rng.uniform(50, 60))
    gap = float(rng.uniform(ctx.tolerances.length_eps_mm, t_topo))
    loops.append(_box(x0, 0, x0 + 5, 5))
    loops.append(_box(x0 + 5 + gap, 0, x0 + 10, 5))  # features between eps_len and t_topo apart
    return loops


@pytest.mark.req("REQ-G2D-030", "REQ-G2D-031")
@pytest.mark.parametrize("seed", range(20))
def test_the_resolution_chain_of_research_test_21(ctx: Context, seed: int) -> None:
    rng = np.random.default_rng(seed)
    points, starts = _layout(_random_loops(rng, ctx))
    result = grid_union(points, starts, ctx)
    assert result.ok, result.diagnostics
    region = result.value
    assert region is not None
    u, t_topo = ctx.tolerances.grid_unit_mm, ctx.tolerances.topology_tol_mm
    # Every output vertex within 2.83 grid units of the input polylines (REQ-G2D-030).
    assert np.isfinite(polyline_distances(region.points, points, starts, 2.83 * u)).all()
    # Point in region agrees farther than t_topo from every boundary (REQ-G2D-031).
    q = rng.uniform(-10, 70, size=(2000, 2))
    far = np.isinf(polyline_distances(q, points, starts, t_topo)) & np.isinf(
        polyline_distances(q, region.points, region.loop_starts, t_topo)
    )
    given = point_in_region(q[far], _rows(points, starts), ctx)
    union = point_in_region(q[far], _rows(region.points, region.loop_starts), ctx)
    assert (given == union).all()
    assert (given != PointLocation.ON).all()


@pytest.mark.req("REQ-G2D-033")
def test_a_translated_input_gives_the_same_union(ctx: Context) -> None:
    points, starts = _layout([_box(0, 0, 10, 10), _box(5, 5, 15, 15), _box(30, 0, 31.00015, 1)])
    here = grid_union(points, starts, ctx).value
    moved = grid_union(points + np.array([3000.0, -2500.0]), starts, ctx).value
    assert here is not None
    assert moved is not None
    assert moved.loop_starts.tolist() == here.loop_starts.tolist()
    back = moved.points - np.array([3000.0, -2500.0])
    assert np.abs(back - here.points).max() <= 6 * ctx.tolerances.grid_unit_mm


@pytest.mark.req("REQ-G2D-034")
@pytest.mark.parametrize(("far", "refused"), [(6700.0, False), (6712.0, True)])
def test_a_span_of_2_to_the_26_grid_units_is_refused(
    ctx: Context, far: float, refused: bool
) -> None:
    points, starts = _layout([_box(0, 0, 1, 1), _box(far, 0, far + 1, 1)])
    result = grid_union(points, starts, ctx)
    if refused:
        assert result.value is None
        assert codes(result) == ["REGION_TOO_LARGE"]
    else:
        assert result.ok, result.diagnostics


@pytest.mark.req("REQ-G2D-034", "REQ-G2D-230")
def test_the_span_limit_is_the_declared_parameter() -> None:
    # Peter, 2026-10-08: a declared foundation parameter, 2^26 grid units, enough for release 1.
    declared = TOLERANCE_DEFAULTS["grid_max_span_units"]
    assert declared.default == 2**26
    assert declared.unit == "grid units"
    assert declared.default == _grid.MAX_SPAN_GRID_UNITS
