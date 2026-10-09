# SPDX-License-Identifier: Apache-2.0
"""Unit tests of the stock update (plan 0005, step 7, part 3): `machined_area` (REQ-OFF-031, 032)
and `stock_layer` (REQ-OFF-031, 044), research 02's test 22."""

import dataclasses
import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes, reversed_loop
from offset2d_oracles import distance_to_curves, inside_region, polygon_rows
from offset2d_strategies import circle, rounded_box, to_curve_rows
from splintercam.foundation import (
    CANCELLED,
    TOLERANCE_DEFAULTS,
    CancellationToken,
    Context,
    ToleranceSet,
)
from splintercam.geometry2d import CurveRows, PointLocation, PolygonRegion, point_in_region
from splintercam.offset2d import EdgeClass, SourceClasses, machined_area, stock_layer

NAN = math.nan
Chain = tuple[NDArray[np.float64], NDArray[np.int64]]


def chain(rows: list[list[float]], first_id: int) -> Chain:
    return np.array(rows, dtype=np.float64), first_id + np.arange(len(rows), dtype=np.int64)


def as_curves(path: Chain) -> CurveRows:
    """An open chain as curve rows for the distance oracle (its rows only, no closing edge)."""
    return CurveRows(path[0], path[1], np.array([0], dtype=np.int64))


def classes_for(*id_arrays: NDArray[np.int64]) -> SourceClasses:
    ids = np.unique(np.concatenate(id_arrays))
    return SourceClasses(ids, np.full(ids.size, int(EdgeClass.CLEARED), dtype=np.int8))


def m_mm(ctx: Context) -> float:
    """m = t_flat + 6u (REQ-OFF-032), the 6 the declared rounding margin (D-132)."""
    margin = TOLERANCE_DEFAULTS["rounding_margin_grid_units"].default
    return ctx.tolerances.flatten_tol_mm + margin * ctx.tolerances.grid_unit_mm


def with_tol(ctx: Context, tol_mm: float) -> Context:
    built = ToleranceSet.for_operation(tol_mm)
    assert built.value is not None
    return dataclasses.replace(ctx, tolerances=built.value)


def inside(points: NDArray[np.float64], region: PolygonRegion, ctx: Context) -> NDArray[np.bool_]:
    if region.loop_starts.size == 0:
        return np.zeros(points.shape[0], dtype=bool)
    located: NDArray[np.int8] = point_in_region(
        points, polygon_rows(region.points, region.loop_starts), ctx
    )
    return located == PointLocation.IN


def densified(region: PolygonRegion, per_edge: int = 8) -> NDArray[np.float64]:
    """Points along every edge of the region, its vertices among them."""
    rows = polygon_rows(region.points, region.loop_starts).rows
    t = np.linspace(0.0, 1.0, per_edge, endpoint=False)[None, :, None]
    return (rows[:, None, 0:2] * (1.0 - t) + rows[:, None, 2:4] * t).reshape(-1, 2)


PATHS = {
    "straight": [[0.0, 0.0, 100.0, 0.0, NAN, NAN, 0.0]],
    "ccw arc": [[10.0, 0.0, 0.0, 10.0, 0.0, 0.0, math.pi / 2]],
    "cw arc": [[0.0, 10.0, 10.0, 0.0, 0.0, 0.0, -math.pi / 2]],
    "closed": [[0.0, 0.0, 30.0, 0.0, NAN, NAN, 0.0], [30.0, 0.0, 30.0, 20.0, NAN, NAN, 0.0],
               [30.0, 20.0, 0.0, 20.0, NAN, NAN, 0.0], [0.0, 20.0, 0.0, 0.0, NAN, NAN, 0.0]],
}  # fmt: skip


@pytest.mark.req("REQ-OFF-032")
@pytest.mark.parametrize("name", list(PATHS))
@pytest.mark.parametrize("tol_mm", [0.01, 0.05])
def test_the_machined_area_lies_in_its_band(name: str, tol_mm: float, ctx: Context) -> None:
    # REQ-OFF-032: grown by δ = R - m with round joins and ends, no bias. Measured from the true
    # path the boundary lies in [R - m - a - 3u - t_flat, R - 3u]: the flattening lies up to t_flat
    # off the true path on either side, the joins' chords up to a inside, the rounding 3u either
    # way (DEC-OFF-015), so the area never reaches beyond the true sweep of radius R.
    ctx = with_tol(ctx, tol_mm)
    radius, path = 4.0, chain(PATHS[name], 100)
    result = machined_area([path], radius, classes_for(path[1]), ctx)
    assert result.value is not None, result.diagnostics
    tol = ctx.tolerances
    u, a, t_flat = tol.grid_unit_mm, tol.arc_tol_mm, tol.flatten_tol_mm
    d = distance_to_curves(densified(result.value), as_curves(path))
    assert d.min() >= radius - m_mm(ctx) - a - 3.0 * u - t_flat
    assert d.max() <= radius - 3.0 * u
    assert set(result.value.source_ids.tolist()) <= set(path[1].tolist())
    if name == "closed":  # a closed pass sweeps a band: the area has a hole
        assert result.value.loop_starts.size == 2


@pytest.mark.req("REQ-OFF-032", "REQ-OFF-013")
@pytest.mark.parametrize("radius", [math.nan, math.inf, -1.0, 0.0])
def test_a_bad_tool_radius_is_refused(radius: float, ctx: Context) -> None:
    path = chain(PATHS["straight"], 100)
    with pytest.raises(ValueError, match="tool radius"):
        machined_area([path], radius, classes_for(path[1]), ctx)


@pytest.mark.req("REQ-OFF-032")
def test_a_tool_radius_not_above_m_plus_a_is_refused(ctx: Context) -> None:
    # δ = R - m must exceed a, else a round join has no step (DEC-OFF-015).
    path = chain(PATHS["straight"], 100)
    least = m_mm(ctx) + ctx.tolerances.arc_tol_mm
    with pytest.raises(ValueError, match="tool radius"):
        machined_area([path], least, classes_for(path[1]), ctx)
    assert machined_area([path], least * 1.5, classes_for(path[1]), ctx).ok


@pytest.mark.req("REQ-OFF-039")
def test_no_paths_machine_nothing(ctx: Context) -> None:
    result = machined_area([], 5.0, classes_for(np.array([1], np.int64)), ctx)
    assert result.value is not None
    assert result.value.loop_starts.size == 0
    assert codes(result) == ["OFFSET_EMPTY"]


@pytest.mark.req("REQ-OFF-040", "REQ-OFF-013", "REQ-OFF-041")
def test_a_broken_chain_missing_classes_and_cancellation(ctx: Context) -> None:
    broken = chain([[0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0], [11.0, 0.0, 20.0, 0.0, NAN, NAN, 0.0]], 1)
    result = machined_area([broken], 5.0, classes_for(broken[1]), ctx)
    assert result.value is None
    assert codes(result) == ["CURVE_INVALID"]  # build_chain's diagnostic, passed on
    good = chain(PATHS["straight"], 100)
    with pytest.raises(ValueError, match="class"):
        machined_area([good], 5.0, classes_for(np.array([1], np.int64)), ctx)
    cancel = CancellationToken()
    cancel.cancel()
    cancelled = dataclasses.replace(ctx, cancel=cancel)
    assert machined_area([good], 5.0, classes_for(good[1]), cancelled).diagnostics == (CANCELLED,)
    raw = to_curve_rows([rounded_box(0.0, 0.0, 10.0, 10.0, 0.0)], ctx)
    assert stock_layer(raw, [], classes_for(raw.ids), cancelled).diagnostics == (CANCELLED,)


@pytest.mark.req("REQ-OFF-031")
def test_paths_spanning_the_limit_when_grown_are_refused(ctx: Context) -> None:
    # 6700 mm of path grown by about 6 mm on both sides passes 2^26 grid units (about 6711 mm).
    path = chain([[0.0, 0.0, 6700.0, 0.0, NAN, NAN, 0.0]], 100)
    result = machined_area([path], 6.0, classes_for(path[1]), ctx)
    assert result.value is None
    assert codes(result) == ["REGION_TOO_LARGE"]
    assert machined_area([path], 4.5, classes_for(path[1]), ctx).ok  # 6700 + 2·4.5 fits


def _test_22(ctx: Context) -> tuple[CurveRows, list[Chain]]:
    raw = to_curve_rows([rounded_box(0.0, 0.0, 100.0, 60.0, 10.0)], ctx)  # corners with arcs
    pocket = chain(
        [[20.0, 15.0, 45.0, 15.0, NAN, NAN, 0.0], [45.0, 15.0, 45.0, 40.0, NAN, NAN, 0.0],
         [45.0, 40.0, 20.0, 40.0, NAN, NAN, 0.0], [20.0, 40.0, 20.0, 15.0, NAN, NAN, 0.0]],
        200,
    )  # fmt: skip  # a closed pocket pass
    profile = chain(
        [[70.0, -10.0, 70.0, 30.0, NAN, NAN, 0.0],
         [70.0, 30.0, 80.0, 40.0, 80.0, 30.0, -math.pi / 2],
         [80.0, 40.0, 80.0, 70.0, NAN, NAN, 0.0]],
        300,
    )  # fmt: skip  # an open profile with an arc
    return raw, [pocket, profile]


def _near_the_bands(
    raw: CurveRows, paths: list[Chain], radius: float, bound: float
) -> NDArray[np.float64]:
    """Points within a few bounds of the cut's edge (distance R from a path) or of the raw
    boundary, where a wrong m or a wrong flattening side would show; and 10^4 anywhere."""
    rng = np.random.default_rng(22)
    candidates = rng.uniform((-5.0, -5.0), (105.0, 65.0), size=(400_000, 2))
    d_cut = np.minimum(*[distance_to_curves(candidates, as_curves(p)) for p in paths])
    d_raw = distance_to_curves(candidates, raw)
    near = (np.abs(d_cut - radius) < 4.0 * bound) | (d_raw < 4.0 * bound)
    return np.concatenate([candidates[near], candidates[:10_000]])


@pytest.mark.req("REQ-OFF-044", "REQ-OFF-032")
def test_the_stock_after_a_pocket_and_a_profile(ctx: Context) -> None:
    # Research 02, test 22: a 100 x 60 mm layer with round corners, a pocket pass and a profile,
    # both with R = 5. Never less stock than the exact geometry leaves: every point inside the
    # true layer and farther than R from every path is stock, but for the rounding of the layer's
    # boundary to the grid, within 1u (DEC-OFF-015). Too much stock only within 2·t_flat + a + 12u
    # (DEC-OFF-007). The other order gives the same arrays.
    raw, paths = _test_22(ctx)
    radius = 5.0
    classes = classes_for(raw.ids, *[p[1] for p in paths])
    areas = [machined_area([p], radius, classes, ctx).value for p in paths]
    machined = [a for a in areas if a is not None]
    assert len(machined) == 2
    layer = stock_layer(raw, machined, classes, ctx)
    other = stock_layer(raw, machined[::-1], classes, ctx)
    assert layer.value is not None, codes(layer)
    assert other.value is not None
    for field in ("points", "loop_starts", "source_ids", "fixed"):
        assert getattr(layer.value, field).tobytes() == getattr(other.value, field).tobytes()
    tol = ctx.tolerances
    bound = 2.0 * tol.flatten_tol_mm + tol.arc_tol_mm + 12.0 * tol.grid_unit_mm
    points = _near_the_bands(raw, paths, radius, bound)
    d_raw = distance_to_curves(points, raw)
    d_cut = np.minimum(*[distance_to_curves(points, as_curves(p)) for p in paths])
    in_raw = inside_region(points, raw)
    got = inside(points, layer.value, ctx)
    oracle_slack = 1e-9  # the distance oracle's own error, far below u
    exact_stock = in_raw & (d_raw > tol.grid_unit_mm) & (d_cut > radius + oracle_slack)
    assert got[exact_stock].all()
    cut_away = (d_cut < radius - bound) | (~in_raw & (d_raw > bound))
    assert not got[cut_away].any()


@pytest.mark.req("REQ-OFF-044")
def test_no_machined_area_leaves_the_raw_layer(ctx: Context) -> None:
    raw = to_curve_rows([rounded_box(0.0, 0.0, 100.0, 60.0, 0.0)], ctx)
    layer = stock_layer(raw, [], classes_for(raw.ids), ctx)
    assert layer.value is not None
    assert layer.value.loop_starts.size == 1


@pytest.mark.req("REQ-OFF-044", "REQ-OFF-039")
def test_a_layer_machined_away_is_empty(ctx: Context) -> None:
    raw = to_curve_rows([rounded_box(0.0, 0.0, 4.0, 4.0, 0.0)], ctx)
    path = chain([[2.0, 2.0, 2.0, 2.0 + 1e-3, NAN, NAN, 0.0]], 100)
    classes = classes_for(raw.ids, path[1])
    area = machined_area([path], 5.0, classes, ctx).value
    assert area is not None
    layer = stock_layer(raw, [area], classes, ctx)
    assert layer.value is not None
    assert layer.value.loop_starts.size == 0
    assert codes(layer) == ["OFFSET_EMPTY"]


@pytest.mark.req("REQ-OFF-031", "REQ-OFF-040")
def test_a_raw_layer_too_large_or_with_crossing_loops(ctx: Context) -> None:
    huge = to_curve_rows([rounded_box(0.0, 0.0, 6712.0, 10.0, 0.0)], ctx)
    assert codes(stock_layer(huge, [], classes_for(huge.ids), ctx)) == ["REGION_TOO_LARGE"]
    crossing = to_curve_rows(
        [rounded_box(0.0, 0.0, 10.0, 10.0, 0.0), rounded_box(5.0, 5.0, 15.0, 15.0, 0.0)], ctx
    )
    result = stock_layer(crossing, [], classes_for(crossing.ids), ctx)
    assert result.value is None
    assert codes(result) == ["LOOPS_CROSS"]


@pytest.mark.req("REQ-OFF-044")
def test_a_raw_layer_with_a_hole_keeps_it(ctx: Context) -> None:
    raw = to_curve_rows(
        [rounded_box(0.0, 0.0, 60.0, 40.0, 5.0), reversed_loop(circle(30.0, 20.0, 8.0, 0.3, 2))],
        ctx,
    )
    layer = stock_layer(raw, [], classes_for(raw.ids), ctx).value
    assert layer is not None
    assert layer.loop_starts.size == 2
