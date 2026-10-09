# SPDX-License-Identifier: Apache-2.0
"""Unit tests of `grow_chain` (plan 0005, step 8, part 1): research 02's test 13, a chain with
an arc, a closed chain and the refusals."""

import dataclasses
import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes
from offset2d_oracles import distance_to_curves, polygon_rows
from splintercam.foundation import CANCELLED, TOLERANCE_DEFAULTS, CancellationToken, Context
from splintercam.geometry2d import (
    AirSide,
    CurveRows,
    PointLocation,
    PolygonRegion,
    build_chain,
    point_in_region,
)
from splintercam.offset2d import EdgeClass, SourceClasses, grow_chain

NAN = math.nan
LINE = [[0.0, 0.0, 100.0, 0.0, NAN, NAN, 0.0]]
WITH_ARC = [[0.0, 0.0, 20.0, 0.0, NAN, NAN, 0.0], [20.0, 0.0, 30.0, 10.0, 20.0, 10.0, math.pi / 2],
            [30.0, 10.0, 30.0, 30.0, NAN, NAN, 0.0]]  # fmt: skip


def rows_ids(rows: list[list[float]]) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    return np.array(rows, dtype=np.float64), 100 + np.arange(len(rows), dtype=np.int64)


def classes(ids: NDArray[np.int64]) -> SourceClasses:
    return SourceClasses(ids, np.full(ids.size, int(EdgeClass.AIR), dtype=np.int8))


def grown(rows: list[list[float]], t_mm: float, ctx: Context) -> PolygonRegion:
    r, i = rows_ids(rows)
    result = grow_chain(r, i, t_mm, classes(i), ctx)
    assert result.value is not None, result.diagnostics
    return result.value


def band_top(t_mm: float, ctx: Context) -> float:
    """t + t_flat + a + 6u (REQ-OFF-027), the 6 the declared rounding margin (D-132)."""
    tol = ctx.tolerances
    margin = TOLERANCE_DEFAULTS["rounding_margin_grid_units"].default * tol.grid_unit_mm
    return t_mm + tol.flatten_tol_mm + tol.arc_tol_mm + margin


def area(region: PolygonRegion) -> float:
    x, y = region.points[:, 0], region.points[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


@pytest.mark.req("REQ-OFF-027")
def test_a_straight_rapid_grows_into_its_stadium(ctx: Context) -> None:
    # Research 02, test 13: (0, 0) to (100, 0) grown by 6 is the stadium of area 1200 + 36π,
    # every vertex within [t, t + t_flat + a + 6u] of the chain.
    region = grown(LINE, 6.0, ctx)
    assert region.loop_starts.tolist() == [0]
    d = distance_to_curves(region.points, CurveRows(*rows_ids(LINE), np.array([0])))
    assert d.min() >= 6.0
    assert d.max() <= band_top(6.0, ctx)
    # The stadium of radius t, grown by at most t_flat + a + 6u more (the band's top).
    top = band_top(6.0, ctx)
    assert 1200.0 + 36.0 * math.pi <= area(region) <= 200.0 * top + math.pi * top**2
    assert set(region.source_ids.tolist()) == {100}


@pytest.mark.req("REQ-OFF-027")
@pytest.mark.parametrize("t_mm", [0.5, 6.0])
def test_every_point_within_t_of_a_chain_with_an_arc_is_inside(t_mm: float, ctx: Context) -> None:
    # REQ-OFF-027: the flattening of the arc lies up to t_flat inside it on one side; δ adds t_flat,
    # so every point within t of the true chain lies in the result, on both sides of the arc.
    region = grown(WITH_ARC, t_mm, ctx)
    chain = CurveRows(*rows_ids(WITH_ARC), np.array([0]))
    rng = np.random.default_rng(13)
    points = rng.uniform((-t_mm - 1.0, -t_mm - 1.0), (31.0 + t_mm, 31.0 + t_mm), size=(40_000, 2))
    d = distance_to_curves(points, chain)
    near = points[d <= t_mm - 1e-9]  # within t, but for the oracle's own error
    located = point_in_region(near, polygon_rows(region.points, region.loop_starts), ctx)
    assert (located == PointLocation.IN).all()
    # The band [t, t + t_flat + a + 6u] is measured from the flattened chain (REQ-OFF-027).
    flat = build_chain(*rows_ids(WITH_ARC), AirSide.LEFT, ctx).value
    assert flat is not None
    lines = np.full((flat.points.shape[0] - 1, 3), [NAN, NAN, 0.0])  # cx, cy, sweep of a line
    flat_rows = np.column_stack([flat.points[:-1], flat.points[1:], lines])
    flat_chain = CurveRows(flat_rows, flat.source_ids, np.array([0]))
    vertices = distance_to_curves(region.points, flat_chain)
    assert vertices.min() >= t_mm
    assert vertices.max() <= band_top(t_mm, ctx)


@pytest.mark.req("REQ-OFF-029")
def test_a_closed_chain_is_refused(ctx: Context) -> None:
    square = [
        [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0],
        [10.0, 0.0, 10.0, 10.0, NAN, NAN, 0.0],
        [10.0, 10.0, 0.0, 10.0, NAN, NAN, 0.0],
        [0.0, 10.0, 0.0, 0.0, NAN, NAN, 0.0],
    ]
    r, i = rows_ids(square)
    result = grow_chain(r, i, 1.0, classes(i), ctx)
    assert result.value is None
    assert codes(result) == ["CHAIN_CLOSED"]


@pytest.mark.req("REQ-OFF-013")
@pytest.mark.parametrize("t_mm", [0.0, -1.0, math.nan, math.inf])
def test_a_clearance_not_above_0_and_finite_is_refused(t_mm: float, ctx: Context) -> None:
    r, i = rows_ids(LINE)
    with pytest.raises(ValueError, match="clearance"):
        grow_chain(r, i, t_mm, classes(i), ctx)


@pytest.mark.req("REQ-OFF-013", "REQ-OFF-040", "REQ-OFF-041")
def test_missing_classes_a_broken_chain_and_cancellation(ctx: Context) -> None:
    r, i = rows_ids(LINE)
    with pytest.raises(ValueError, match="class"):
        grow_chain(r, i, 1.0, classes(np.array([1], np.int64)), ctx)
    broken = rows_ids([[0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0], [11.0, 0.0, 20.0, 0.0, NAN, NAN, 0.0]])
    assert codes(grow_chain(*broken, 1.0, classes(broken[1]), ctx)) == ["CURVE_INVALID"]
    cancel = CancellationToken()
    cancel.cancel()
    cancelled = dataclasses.replace(ctx, cancel=cancel)
    assert grow_chain(r, i, 1.0, classes(i), cancelled).diagnostics == (CANCELLED,)


@pytest.mark.req("REQ-OFF-031")
def test_a_chain_spanning_the_limit_when_grown_is_refused(ctx: Context) -> None:
    r, i = rows_ids([[0.0, 0.0, 6700.0, 0.0, NAN, NAN, 0.0]])
    assert codes(grow_chain(r, i, 6.0, classes(i), ctx)) == ["REGION_TOO_LARGE"]
    assert grow_chain(r, i, 4.0, classes(i), ctx).ok
