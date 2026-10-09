# SPDX-License-Identifier: Apache-2.0
"""Unit tests of `offset_region`'s source IDs and order (plan 0005, step 6): research 02's test 14,
the class order of D-059, and the same arrays for the same input in any loop order."""

import numpy as np
import pytest

from geometry2d_checks import reversed_loop
from offset2d_oracles import polygon_rows
from offset2d_strategies import circle, rounded_box, to_curve_rows
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows, PolygonRegion, RegionKind, curve_rows
from splintercam.offset2d import EdgeClass, SourceClasses, offset_region

AIR, MATERIAL = RegionKind.AIR, RegionKind.MATERIAL


def classes(loops: CurveRows, kind: EdgeClass = EdgeClass.MATERIAL) -> SourceClasses:
    ids = np.unique(loops.ids)
    return SourceClasses(ids, np.full(ids.size, int(kind), dtype=np.int8))


def offset(loops: CurveRows, kind: RegionKind, t_mm: float, ctx: Context) -> PolygonRegion:
    result = offset_region(loops, kind, t_mm, classes(loops), ctx)
    assert result.value is not None, result.diagnostics
    return result.value


def box_loop(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return rounded_box(x0, y0, x1, y1, 0.0)


@pytest.mark.req("REQ-OFF-034")
def test_every_vertex_carries_an_input_id(ctx: Context) -> None:
    loops = to_curve_rows([rounded_box(0.0, 0.0, 60.0, 40.0, 5.0)], ctx)
    region = offset(loops, AIR, 3.0, ctx)
    assert set(region.source_ids.tolist()) <= set(loops.ids.tolist())
    assert polygon_rows(region.points, region.loop_starts).rows.shape[0] == region.points.shape[0]


def rectangle_with_ids(ids: list[int], ctx: Context) -> CurveRows:
    """The 60 x 40 rectangle of test 14 with chosen source IDs: right, top, left, bottom."""
    rows = np.array(box_loop(0.0, 0.0, 60.0, 40.0))
    built = curve_rows(rows, np.array(ids, dtype=np.int64), np.array([0], np.int64), ctx)
    assert built.value is not None, built.diagnostics
    return built.value


def ids_by_place(region: PolygonRegion) -> dict[str, set[int]]:
    """The source IDs of the grown rectangle's edges, by where their midpoints lie."""
    rows = polygon_rows(region.points, region.loop_starts).rows
    x, y = (rows[:, 0] + rows[:, 2]) / 2.0, (rows[:, 1] + rows[:, 3]) / 2.0
    places = {
        "top-right": (y > 40.0) & (x > 60.0), "top-left": (y > 40.0) & (x < 0.0),
        "bottom-left": (y < 0.0) & (x < 0.0), "bottom-right": (y < 0.0) & (x > 60.0),
        "top": (y > 40.0) & (x >= 0.0) & (x <= 60.0),
        "right": (x > 60.0) & (y >= 0.0) & (y <= 40.0),
        "left": (x < 0.0) & (y >= 0.0) & (y <= 40.0),
        "bottom": (y < 0.0) & (x >= 0.0) & (x <= 60.0),
    }  # fmt: skip
    return {name: set(region.source_ids[mask].tolist()) for name, mask in places.items()}


@pytest.mark.req("REQ-OFF-034")
def test_edges_carry_their_source_ids_and_ties_go_to_material(ctx: Context) -> None:
    # Research 02, test 14: a 60 x 40 rectangle of material, its top edge tagged air, grown by 5.
    # Straight edges carry their own side's ID; the round joins at the top corners tie a side
    # (material) with the top (air), which material wins (D-059) although the top has the lower,
    # here negative, ID; the bottom joins tie two material edges, which the lower ID wins, here
    # the bottom's (5), whose segment comes after the left side's (9).
    m, a = EdgeClass.MATERIAL, EdgeClass.AIR
    loops = rectangle_with_ids([7, -4, 9, 5], ctx)
    classes_ = SourceClasses(np.array([-4, 5, 7, 9]), np.array([a, m, m, m], dtype=np.int8))
    region = offset_region(loops, MATERIAL, 5.0, classes_, ctx).value
    assert region is not None
    assert ids_by_place(region) == {
        "top-right": {7}, "top-left": {9}, "bottom-left": {5}, "bottom-right": {5},
        "top": {-4}, "right": {7}, "left": {9}, "bottom": {5},
    }  # fmt: skip


@pytest.mark.req("REQ-OFF-034")
def test_cleared_wins_over_air_and_material_over_cleared(ctx: Context) -> None:
    # The full class order of D-059, each winner with the higher ID: right material (8) against
    # top cleared (2) at the top-right join, top cleared (2) against left air (1) at the top-left.
    m, c, a = EdgeClass.MATERIAL, EdgeClass.CLEARED, EdgeClass.AIR
    loops = rectangle_with_ids([8, 2, 1, 3], ctx)
    classes_ = SourceClasses(np.array([1, 2, 3, 8]), np.array([a, c, m, m], dtype=np.int8))
    region = offset_region(loops, MATERIAL, 5.0, classes_, ctx).value
    assert region is not None
    places = ids_by_place(region)
    assert places["top-right"] == {8}
    assert places["top-left"] == {2}


@pytest.mark.req("REQ-OFF-011", "REQ-OFF-038")
@pytest.mark.parametrize("kind", [AIR, MATERIAL])
def test_the_same_input_gives_the_same_arrays_in_any_loop_order(
    kind: RegionKind, ctx: Context
) -> None:
    # Research 02, test 19 on one platform: bit for bit, also with the loops given in another
    # order and turned round (REQ-OFF-038: the order does not follow Clipper2's).
    wall = rounded_box(0.0, 0.0, 90.0, 60.0, 8.0)
    islands = [
        reversed_loop(circle(25.0, 30.0, 6.0, 0.3, 2)),
        reversed_loop(box_loop(55.0, 20.0, 70.0, 40.0)),
    ]
    first = offset(to_curve_rows([wall, *islands], ctx), kind, 2.5, ctx)
    again = offset(to_curve_rows([wall, *islands], ctx), kind, 2.5, ctx)
    turned = [reversed_loop(islands[1]), wall, islands[0]]  # another order, one loop reversed
    other = offset(to_curve_rows(turned, ctx), kind, 2.5, ctx)
    for a, b in ((first, again), (first, other)):
        assert a.points.tobytes() == b.points.tobytes()
        assert a.loop_starts.tobytes() == b.loop_starts.tobytes()
        assert a.fixed.tobytes() == b.fixed.tobytes()
    # The IDs follow the input rows, which the other order renumbers: compared for the same input.
    assert first.source_ids.tobytes() == again.source_ids.tobytes()
    # The canonical order itself: each loop starts at its smallest point, by x then y, and the
    # loops ascend by that point (REQ-OFF-038; DEC-G2D-036, 042).
    starts = first.loop_starts.tolist()
    ends = [*starts[1:], first.points.shape[0]]
    firsts = [tuple(first.points[a].tolist()) for a in starts]
    for (a, b), start in zip(zip(starts, ends, strict=True), firsts, strict=True):
        assert start == min(tuple(p) for p in first.points[a:b].tolist())
    assert firsts == sorted(firsts)
