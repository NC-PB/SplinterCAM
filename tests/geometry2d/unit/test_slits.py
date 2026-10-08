# SPDX-License-Identifier: Apache-2.0
"""Unit tests of zero-width slits in loops (REQ-G2D-241; Peter, 2026-10-08, DEC-G2D-039)."""

import math

import numpy as np
import pytest

from geometry2d_checks import codes, polygons
from splintercam.foundation import Context
from splintercam.geometry2d import (
    CurveRows,
    LoopTree,
    RegionKind,
    build_region,
    curve_rows,
    loop_tree,
)

Points = list[tuple[float, float]]
NAN = math.nan

# A square with a square hole, drawn as one loop: in along the slit (20, 10) to (14, 10), round
# the hole clockwise, and back out along the slit.
KEYHOLE: Points = [
    (0, 0), (20, 0), (20, 10), (14, 10), (14, 6), (6, 6), (6, 14), (14, 14), (14, 10), (20, 10),
    (20, 20), (0, 20),
]  # fmt: skip


def _tree(loops: CurveRows, ctx: Context) -> LoopTree:
    result = loop_tree(loops, ctx)
    assert result.ok, result.diagnostics
    assert result.value is not None
    return result.value


def _pieces(tree: LoopTree) -> frozenset[frozenset[tuple[float, ...]]]:
    """The tree's loops as sets of rows, whatever row each loop starts with."""
    ends = [*tree.loops.row_starts[1:].tolist(), tree.loops.rows.shape[0]]
    loops = zip(tree.loops.row_starts.tolist(), ends, strict=True)
    rounded = np.nan_to_num(tree.loops.rows, nan=-1.0)  # lines' NaN centres compare equal
    return frozenset(frozenset(map(tuple, rounded[a:b].tolist())) for a, b in loops)


@pytest.mark.req("REQ-G2D-241")
def test_a_keyhole_is_split_into_its_outer_loop_and_its_hole(ctx: Context) -> None:
    result = loop_tree(polygons([KEYHOLE], ctx), ctx)
    assert result.ok
    tree = result.value
    assert tree is not None
    assert tree.depth.tolist() == [0, 1]
    assert tree.parent.tolist() == [-1, 0]
    assert tree.input_index.tolist() == [0, 0]
    assert tree.loops.row_starts.tolist() == [0, 5]  # the outer loop's 5 rows, the hole's 5
    assert codes(result) == ["LOOP_SLIT"]
    note = result.diagnostics[0]
    assert note.location == "loop 0"
    assert "(20, 10)" in note.message
    assert "(14, 10)" in note.message


@pytest.mark.req("REQ-G2D-241")
@pytest.mark.parametrize("start", range(len(KEYHOLE)))
@pytest.mark.parametrize("backward", [False, True])
def test_the_split_is_the_same_from_every_start_and_direction(
    ctx: Context, start: int, backward: bool
) -> None:
    turned = KEYHOLE[start:] + KEYHOLE[:start]
    given = _tree(polygons([turned[::-1] if backward else turned], ctx), ctx)
    expected = _tree(polygons([KEYHOLE], ctx), ctx)
    assert _pieces(given) == _pieces(expected)
    assert sorted(given.depth.tolist()) == [0, 1]


@pytest.mark.req("REQ-G2D-241")
def test_a_keyhole_with_a_round_hole_keeps_its_circle(ctx: Context) -> None:
    rows = np.array(
        [
            [0, 0, 20, 0, NAN, NAN, 0.0],
            [20, 0, 20, 10, NAN, NAN, 0.0],
            [20, 10, 14, 10, NAN, NAN, 0.0],
            [14, 10, 14, 10, 10, 10, -math.tau],  # the hole, clockwise
            [14, 10, 20, 10, NAN, NAN, 0.0],
            [20, 10, 20, 20, NAN, NAN, 0.0],
            [20, 20, 0, 20, NAN, NAN, 0.0],
            [0, 20, 0, 0, NAN, NAN, 0.0],
        ]
    )
    built = curve_rows(rows, np.arange(8, dtype=np.int64), np.zeros(1, np.int64), ctx)
    assert built.value is not None
    tree = _tree(built.value, ctx)
    assert tree.depth.tolist() == [0, 1]
    assert tree.loops.ids.tolist() == [5, 6, 7, 0, 1, 3]  # the slit's rows 2 and 4 removed


@pytest.mark.req("REQ-G2D-241")
def test_a_slit_of_two_rows_each_way_is_removed(ctx: Context) -> None:
    slit = [*KEYHOLE[:3], (17, 10), *KEYHOLE[3:9], (17, 10), *KEYHOLE[9:]]
    result = loop_tree(polygons([slit], ctx), ctx)
    assert codes(result) == ["LOOP_SLIT"]
    assert result.value is not None
    assert _pieces(result.value) == _pieces(_tree(polygons([KEYHOLE], ctx), ctx))


@pytest.mark.req("REQ-G2D-241")
def test_a_slit_to_a_shape_beside_the_loop_gives_two_loops_side_by_side(ctx: Context) -> None:
    bridge: Points = [
        (0, 0), (10, 0), (10, 5), (20, 5), (20, 0), (30, 0), (30, 10), (20, 10), (20, 5), (10, 5),
        (10, 10), (0, 10),
    ]  # fmt: skip
    tree = _tree(polygons([bridge], ctx), ctx)
    assert tree.depth.tolist() == [0, 0]


@pytest.mark.req("REQ-G2D-241")
def test_a_slit_inside_a_slit_gives_three_nested_loops(ctx: Context) -> None:
    nested: Points = [
        (0, 0), (30, 0), (30, 15), (24, 15), (24, 6), (6, 6), (6, 15), (10, 15), (10, 10),
        (20, 10), (20, 20), (10, 20), (10, 15), (6, 15), (6, 24), (24, 24), (24, 15), (30, 15),
        (30, 30), (0, 30),
    ]  # fmt: skip
    result = loop_tree(polygons([nested], ctx), ctx)
    assert codes(result) == ["LOOP_SLIT", "LOOP_SLIT"]
    assert result.value is not None
    assert sorted(result.value.depth.tolist()) == [0, 1, 2]


@pytest.mark.req("REQ-G2D-241")
def test_a_loop_that_only_runs_back_over_itself_is_no_slit(ctx: Context) -> None:
    there_and_back: Points = [(0, 0), (5, 0), (10, 0), (5, 0)]
    result = loop_tree(polygons([there_and_back], ctx), ctx)
    assert "LOOP_SLIT" not in codes(result)
    assert result.value is not None
    assert result.value.loops.rows.shape[0] == 0


@pytest.mark.req("REQ-G2D-241", "REQ-G2D-238")
def test_a_slit_whose_way_back_takes_other_rows_still_crosses(ctx: Context) -> None:
    # Provisional (DEC-G2D-033): out in one row, back in two, so no row is another's reverse.
    other_way = [*KEYHOLE[:9], (17, 10), *KEYHOLE[9:]]
    result = loop_tree(polygons([other_way], ctx), ctx)
    assert codes(result) == ["LOOPS_CROSS"]


@pytest.mark.req("REQ-G2D-241", "REQ-G2D-176")
def test_build_region_machines_the_keyhole_with_its_hole(ctx: Context) -> None:
    result = build_region(polygons([KEYHOLE], ctx), RegionKind.MATERIAL, ctx)
    assert result.ok
    assert codes(result) == ["LOOP_SLIT"]
    assert result.value is not None
    region = result.value.region
    assert region.loop_starts.size == 2
    area = 0.0
    for p in np.split(region.points, region.loop_starts[1:]):  # per loop: CCW +, CW -
        q = np.roll(p, -1, axis=0)
        area += 0.5 * float((p[:, 0] * q[:, 1] - q[:, 0] * p[:, 1]).sum())
    assert area == pytest.approx(400.0 - 64.0)
