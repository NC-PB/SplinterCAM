# SPDX-License-Identifier: Apache-2.0
"""Unit tests of the machining region (research 01, Loop tree, rule 7; tests 7 and 16)."""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes, polygons
from splintercam.foundation import Context
from splintercam.geometry2d import (
    CurveRows,
    FlatRegion,
    RegionKind,
    build_region,
    curve_rows,
    point_in_region,
)
from splintercam.geometry2d._grid import FillRule, region_with_fill_rule
from splintercam.geometry2d._loops import flatten_loops
from splintercam.geometry2d._tree import loop_tree

Points = list[tuple[float, float]]
NAN = math.nan


def _box(x0: float, y0: float, x1: float, y1: float) -> Points:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _region(loops: CurveRows, ctx: Context, kind: RegionKind = RegionKind.MATERIAL) -> FlatRegion:
    result = build_region(loops, kind, ctx)
    assert result.ok, result.diagnostics
    assert result.value is not None
    return result.value


def _rows_of(points: NDArray[np.float64], starts: NDArray[np.int64]) -> CurveRows:
    ends = np.append(starts[1:], points.shape[0])
    rows: list[list[float]] = []
    for a, b in zip(starts.tolist(), ends.tolist(), strict=True):
        loop: list[list[float]] = points[a:b].tolist()
        rows += [[*p, *q, NAN, NAN, 0.0] for p, q in zip(loop, loop[1:] + loop[:1], strict=True)]
    return CurveRows(np.array(rows), np.arange(len(rows), dtype=np.int64), starts)


def _area(points: NDArray[np.float64], starts: NDArray[np.int64]) -> float:
    ends = np.append(starts[1:], points.shape[0])
    total = 0.0
    for a, b in zip(starts.tolist(), ends.tolist(), strict=True):
        p = points[a:b]
        q = np.roll(p, -1, axis=0)
        total += 0.5 * float((p[:, 0] * q[:, 1] - q[:, 0] * p[:, 1]).sum())
    return total


NESTED = [_box(0, 0, 30, 30), _box(5, 5, 25, 25), _box(10, 10, 20, 20), _box(40, 0, 50, 10)]


@pytest.mark.req("REQ-G2D-176", "REQ-G2D-178", "REQ-G2D-179", "REQ-G2D-124")
def test_the_region_and_the_tree_agree_away_from_the_boundaries(ctx: Context) -> None:
    loops = polygons(NESTED, ctx)
    flat = _region(loops, ctx)
    assert flat.extra_clearance_mm == 0.0
    region = flat.region
    rng = np.random.default_rng(3)
    q = rng.uniform(-5, 55, size=(4000, 2))
    tree = loop_tree(loops, ctx).value
    assert tree is not None
    from splintercam.geometry2d._distances import polyline_distances

    t_topo = ctx.tolerances.topology_tol_mm
    boundary = np.array([p for box in NESTED for p in box], dtype=np.float64)
    starts = np.arange(0, 16, 4, dtype=np.int64)
    far = np.isinf(polyline_distances(q, boundary, starts, t_topo))
    on_tree = point_in_region(q[far], tree.loops, ctx)
    on_region = point_in_region(q[far], _rows_of(region.points, region.loop_starts), ctx)
    assert (on_tree == on_region).all()
    # Loop by loop: the parity of each loop's depth is the region loop's orientation (REQ-179).
    ends = np.append(region.loop_starts[1:], region.points.shape[0])
    signs = sorted(
        (float(region.points[a:b, 0].min()), _area(region.points[a:b], np.zeros(1, np.int64)) > 0)
        for a, b in zip(region.loop_starts.tolist(), ends.tolist(), strict=True)
    )
    assert [ccw for _, ccw in signs] == [True, False, True, True]


@pytest.mark.req("REQ-G2D-177")
def test_the_fill_rules_agree_where_no_flattened_loops_overlap(ctx: Context) -> None:
    tree = loop_tree(polygons(NESTED, ctx), ctx).value
    assert tree is not None
    flat = flatten_loops(tree, RegionKind.MATERIAL, ctx).region
    areas: list[float] = []
    for rule in FillRule:
        joined = region_with_fill_rule(flat, rule, ctx).value
        assert joined is not None
        areas.append(_area(joined.points, joined.loop_starts))
    assert areas[1] == pytest.approx(areas[0], abs=1e-9)
    assert areas[2] == pytest.approx(areas[0], abs=1e-9)


def _circle(cx: float, r: float, sweep: float, start: float = 0.0) -> list[float]:
    x, y = cx + r * math.cos(start), r * math.sin(start)  # one row from the angle `start`
    return [x, y, x, y, cx, 0.0, sweep]


@pytest.mark.req("REQ-G2D-176")
def test_positive_keeps_an_island_overlapping_its_wall_out_of_the_pocket(ctx: Context) -> None:
    # A pocket wall of radius 10 and an island of radius 5 tangent inside it: flattened into the
    # air between them they overlap, with winding -1, which NonZero would count as pocket.
    rows = np.array([_circle(0.0, 10.0, math.tau), _circle(5.0, 5.0, -math.tau)])
    built = curve_rows(rows, np.arange(2, dtype=np.int64), np.array([0, 1], np.int64), ctx)
    assert built.value is not None
    tree = loop_tree(built.value, ctx).value
    assert tree is not None
    flat = flatten_loops(tree, RegionKind.AIR, ctx).region
    positive = region_with_fill_rule(flat, FillRule.POSITIVE, ctx).value
    non_zero = region_with_fill_rule(flat, FillRule.NON_ZERO, ctx).value
    assert positive is not None
    assert non_zero is not None
    assert _area(positive.points, positive.loop_starts) < _area(
        non_zero.points, non_zero.loop_starts
    )


@pytest.mark.req("REQ-G2D-176", "REQ-G2D-181")
def test_an_island_touching_its_hole_at_a_vertex_is_split_and_fixed(ctx: Context) -> None:
    # Research 01, rule 7: Clipper2 2.0.1 joins the island into the hole at their shared vertex
    # (with the island given first; found by probing input orders).
    island = [(25.0, 25.0), (15.0, 20.0), (20.0, 15.0)]
    loops = polygons([island, _box(0, 0, 30, 30), _box(5, 5, 25, 25)], ctx)
    region = _region(loops, ctx).region
    at = (region.points == np.array([25.0, 25.0])).all(axis=1)
    assert at.sum() == 2  # the pinch, once in each split loop
    assert region.fixed[at].tolist() == [1, 1]
    assert region.fixed[~at].sum() == 0
    starts = region.loop_starts
    ends = np.append(starts[1:], region.points.shape[0])
    by_area = sorted(
        _area(region.points[a:b], np.zeros(1, np.int64))
        for a, b in zip(starts.tolist(), ends.tolist(), strict=True)
    )
    assert by_area == pytest.approx([-400.0, 37.5, 900.0])  # the CW hole, the CCW island


@pytest.mark.req("REQ-G2D-176")
def test_an_island_sharing_an_edge_with_its_parent_joins_its_boundary(ctx: Context) -> None:
    loops = polygons([_box(0, 0, 30, 30), _box(0, 10, 5, 20)], ctx)  # a hole on the left wall
    region = _region(loops, ctx).region
    assert region.loop_starts.size == 1  # the notch is part of the outer boundary
    assert _area(region.points, region.loop_starts) == pytest.approx(900.0 - 50.0)


@pytest.mark.req("REQ-G2D-180")
def test_the_vertices_of_a_flattened_arc_carry_the_arcs_id(ctx: Context) -> None:
    rows = np.array(
        [
            [0, 0, 10, 0, NAN, NAN, 0.0],
            [10, 0, 10, 10, 10, 5, math.pi],  # the outward semicircle of research 01, test 16
            [10, 10, 0, 10, NAN, NAN, 0.0],
            [0, 10, 0, 0, NAN, NAN, 0.0],
        ]
    )
    built = curve_rows(rows, np.array([7, 8, 9, 10], np.int64), np.zeros(1, np.int64), ctx)
    assert built.value is not None
    region = _region(built.value, ctx).region
    on_arc = region.points[:, 0] > 10.0 + 1e-6
    assert on_arc.sum() > 10
    # Each output edge, named by the vertex it starts at, carries its own row's ID.
    middle = (region.points + np.roll(region.points, -1, axis=0)) / 2
    x, y = middle[:, 0], middle[:, 1]
    near = 3.0 * ctx.tolerances.grid_unit_mm  # the grid's rounding (REQ-G2D-030)
    expected = np.select(
        [x > 10.0 + near, np.abs(y) < near, np.abs(y - 10.0) < near, np.abs(x) < near],
        [8, 7, 9, 10],
        default=-1,
    )
    assert region.source_ids.tolist() == expected.tolist()


@pytest.mark.req("REQ-G2D-162")
def test_crossing_loops_give_no_region(ctx: Context) -> None:
    beside = _box(30, 0, 40, 10)  # valid on its own
    loops = polygons([_box(0, 0, 10, 10), _box(5, 5, 15, 15), beside], ctx)
    result = build_region(loops, RegionKind.AIR, ctx)
    assert result.value is None
    assert codes(result) == ["LOOPS_CROSS"]


@pytest.mark.req("REQ-G2D-034")
def test_loops_farther_apart_than_the_grid_span_give_no_region(ctx: Context) -> None:
    far = 2.0**26 * ctx.tolerances.grid_unit_mm + 10.0
    loops = polygons([_box(0, 0, 10, 10), _box(far, 0, far + 10, 10)], ctx)
    result = build_region(loops, RegionKind.MATERIAL, ctx)
    assert result.value is None
    assert codes(result) == ["REGION_TOO_LARGE"]


@pytest.mark.req("REQ-G2D-235")
@pytest.mark.parametrize(
    "loop",
    [
        [(0.0, 0.0), (10.0, 0.0), (10.0, 1e-7), (0.0, 1e-7)],  # thin
        [(0.0, 0.0), (1e-5, 0.0), (1e-5, 1e-5), (0.0, 1e-5)],  # smaller than the grid unit
    ],
)
def test_a_region_of_nothing_is_empty_with_a_warning(ctx: Context, loop: Points) -> None:
    result = build_region(polygons([loop], ctx), RegionKind.MATERIAL, ctx)
    assert result.value is not None
    assert result.value.region.loop_starts.size == 0
    assert codes(result) == ["LOOP_DEGENERATE", "REGION_EMPTY"]


@pytest.mark.req("REQ-G2D-118")
@pytest.mark.parametrize("kind", [RegionKind.MATERIAL, RegionKind.AIR])
def test_reversed_loops_give_the_same_region_bit_for_bit(ctx: Context, kind: RegionKind) -> None:
    rows = [
        [0, 0, 10, 0, NAN, NAN, 0.0],
        [10, 0, 10, 10, 10, 5, math.pi],
        [10, 10, 0, 10, 5, 10, -math.pi],
        [0, 10, 0, 0, NAN, NAN, 0.0],
    ]
    backward = [[x1, y1, x0, y0, cx, cy, -s] for x0, y0, x1, y1, cx, cy, s in rows[::-1]]
    flats: list[FlatRegion] = []
    regions: list[FlatRegion] = []
    for given, ids in ((rows, [0, 1, 2, 3]), (backward, [3, 2, 1, 0])):  # each row its own ID
        built = curve_rows(
            np.array(given, dtype=np.float64), np.array(ids, np.int64), np.zeros(1, np.int64), ctx
        )
        assert built.value is not None
        tree = loop_tree(built.value, ctx).value
        assert tree is not None
        flats.append(flatten_loops(tree, kind, ctx))
        regions.append(_region(built.value, ctx, kind))
    for a, b in (flats, regions):
        assert a.region.points.tobytes() == b.region.points.tobytes()
        assert a.region.source_ids.tobytes() == b.region.source_ids.tobytes()


@pytest.mark.req("REQ-G2D-032")
def test_features_closer_than_a_grid_unit_merge_and_stay_merged(ctx: Context) -> None:
    gap = 0.00004  # under half a grid unit: the two squares meet on the grid
    region = _region(polygons([_box(0, 0, 10, 10), _box(10 + gap, 0, 20, 10)], ctx), ctx).region
    assert region.loop_starts.size == 1


def _two_circles(first: list[float], second: list[float], ctx: Context) -> CurveRows:
    rows = np.array([first, second], dtype=np.float64)
    built = curve_rows(rows, np.arange(2, dtype=np.int64), np.array([0, 1], np.int64), ctx)
    assert built.value is not None
    return built.value


def _rule_areas(loops: CurveRows, kind: RegionKind, ctx: Context) -> dict[str, float]:
    """The area of `build_region`'s region and of the region by each fill rule."""
    region = _region(loops, ctx, kind).region
    areas = {"build_region": _area(region.points, region.loop_starts)}
    tree = loop_tree(loops, ctx).value
    assert tree is not None
    flat = flatten_loops(tree, kind, ctx).region
    for rule in FillRule:
        joined = region_with_fill_rule(flat, rule, ctx).value
        assert joined is not None
        areas[rule.name] = _area(joined.points, joined.loop_starts)
    return areas


@pytest.mark.req("REQ-G2D-176")
def test_build_region_keeps_an_island_over_the_pocket_wall_out_of_the_pocket(ctx: Context) -> None:
    # Winding -1 where the circumscribed island leaves the inscribed wall: NonZero would take it
    # as pocket, outside the wall.
    loops = _two_circles(_circle(0.0, 10.0, math.tau), _circle(5.0, 5.0, -math.tau), ctx)
    region = _region(loops, ctx, RegionKind.AIR).region
    reach = 10.0 + 3.0 * ctx.tolerances.grid_unit_mm  # REQ-G2D-030: rounding to the grid
    assert np.hypot(region.points[:, 0], region.points[:, 1]).max() <= reach
    areas = _rule_areas(loops, RegionKind.AIR, ctx)
    assert areas["build_region"] == areas["POSITIVE"]
    assert areas["POSITIVE"] < areas["NON_ZERO"]


@pytest.mark.req("REQ-G2D-176")
def test_two_islands_touching_in_a_pocket_keep_their_overlap_out_of_it(ctx: Context) -> None:
    # Two circumscribed islands, tangent to each other, overlap with winding 1 - 1 - 1 = -1.
    rows = np.array(
        [
            [-20, -20, 20, -20, NAN, NAN, 0.0],
            [20, -20, 20, 20, NAN, NAN, 0.0],
            [20, 20, -20, 20, NAN, NAN, 0.0],
            [-20, 20, -20, -20, NAN, NAN, 0.0],
            _circle(-5.0, 5.0, -math.tau, math.pi / 2),  # no vertex at the tangent point
            _circle(5.0, 5.0, -math.tau, math.pi / 2),
        ]
    )
    built = curve_rows(rows, np.arange(6, dtype=np.int64), np.array([0, 4, 5], np.int64), ctx)
    assert built.value is not None
    areas = _rule_areas(built.value, RegionKind.AIR, ctx)
    assert areas["build_region"] == areas["POSITIVE"]
    assert areas["POSITIVE"] < areas["NON_ZERO"]


@pytest.mark.req("REQ-G2D-176")
def test_an_island_in_a_hole_overlapping_it_stays_material(ctx: Context) -> None:
    # Material with a hole of radius 10 and an island of radius 5 tangent inside it: winding 2
    # where the circumscribed island leaves the inscribed hole, which EvenOdd would cut away.
    rows = np.array(
        [
            [-20, -20, 20, -20, NAN, NAN, 0.0],
            [20, -20, 20, 20, NAN, NAN, 0.0],
            [20, 20, -20, 20, NAN, NAN, 0.0],
            [-20, 20, -20, -20, NAN, NAN, 0.0],
            _circle(0.0, 10.0, -math.tau),
            _circle(5.0, 5.0, math.tau),
        ]
    )
    built = curve_rows(rows, np.arange(6, dtype=np.int64), np.array([0, 4, 5], np.int64), ctx)
    assert built.value is not None
    areas = _rule_areas(built.value, RegionKind.MATERIAL, ctx)
    assert areas["build_region"] == areas["POSITIVE"]
    assert areas["POSITIVE"] > areas["EVEN_ODD"]
