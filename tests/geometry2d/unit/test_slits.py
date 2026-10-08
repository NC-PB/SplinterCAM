# SPDX-License-Identifier: Apache-2.0
"""Unit tests of zero-width slits in loops (REQ-G2D-241; Peter, 2026-10-08, DEC-G2D-039)."""

import math

import numpy as np
import pytest

from geometry2d_checks import codes, polygons
from splintercam.foundation import Context, Severity
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
    assert note.severity is Severity.WARNING
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
    result = loop_tree(polygons([turned[::-1] if backward else turned], ctx), ctx)
    assert codes(result) == ["LOOP_SLIT"]
    assert "from (14, 10) to (20, 10)" in result.diagnostics[0].message  # ends in x, y order
    assert result.value is not None
    expected = _tree(polygons([KEYHOLE], ctx), ctx)
    assert _pieces(result.value) == _pieces(expected)
    assert sorted(result.value.depth.tolist()) == [0, 1]


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
    result = loop_tree(built.value, ctx)
    assert codes(result) == ["LOOP_SLIT"]
    assert "(14, 10) to (20, 10)" in result.diagnostics[0].message
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
    result = loop_tree(polygons([bridge], ctx), ctx)
    assert codes(result) == ["LOOP_SLIT"]
    tree = _tree(polygons([bridge], ctx), ctx)
    assert tree.depth.tolist() == [0, 0]
    assert tree.input_index.tolist() == [0, 0]


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
@pytest.mark.parametrize("length", [2, 3, 4])
def test_a_loop_that_only_runs_back_over_itself_is_no_slit(ctx: Context, length: int) -> None:
    out: Points = [(5.0 * k, 0.0) for k in range(length + 1)]
    there_and_back = out + out[-2:0:-1]  # out over `length` rows and back over the same
    result = loop_tree(polygons([there_and_back], ctx), ctx)
    assert "LOOP_SLIT" not in codes(result)
    assert "LOOPS_CROSS" not in codes(result)
    assert result.value is not None
    assert result.value.loops.rows.shape[0] == 0


@pytest.mark.req("REQ-G2D-241", "REQ-G2D-238")
def test_a_slit_whose_way_back_takes_other_rows_still_crosses(ctx: Context) -> None:
    # Provisional (DEC-G2D-033): out in one row, back in two, so no row is another's reverse.
    other_way = [*KEYHOLE[:9], (17, 10), *KEYHOLE[9:]]
    result = loop_tree(polygons([other_way], ctx), ctx)
    assert codes(result) == ["LOOPS_CROSS"]
    assert result.value is not None
    assert result.value.crossing_points.shape[0] >= 1  # the stretch's ends (REQ-G2D-238)


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


@pytest.mark.req("REQ-G2D-241", "REQ-G2D-209")
@pytest.mark.parametrize("length", [1, 2, 3])
def test_a_spike_of_several_rows_stays_a_spike(ctx: Context, length: int) -> None:
    # Test audit: a run with nothing between its halves is a spike, cleanup's (REQ-G2D-209).
    out: Points = [(10.0, 20.0 - 5.0 * k / length) for k in range(length + 1)]  # down to (10, 15)
    spiked: Points = [(0, 0), (20, 0), (20, 20), *out, *out[-2::-1], (0, 20)]
    result = loop_tree(polygons([spiked], ctx), ctx)
    assert "LOOP_SLIT" not in codes(result)
    assert "CLEANUP_SPIKE" in codes(result)
    assert result.value is not None
    assert result.value.depth.tolist() == [0]


@pytest.mark.req("REQ-G2D-241", "REQ-G2D-236")
def test_a_slit_in_a_later_loop_keeps_that_loops_index(ctx: Context) -> None:
    beside: Points = [(40, 0), (50, 0), (50, 10), (40, 10)]
    result = loop_tree(polygons([beside, KEYHOLE, [(60, 0), (70, 0), (70, 10)]], ctx), ctx)
    assert codes(result) == ["LOOP_SLIT"]
    assert result.diagnostics[0].location == "loop 1"
    assert result.value is not None
    assert result.value.input_index.tolist() == [0, 1, 1, 2]


@pytest.mark.req("REQ-G2D-241", "REQ-G2D-236", "REQ-G2D-162")
def test_a_hole_that_crosses_its_own_outer_loop_crosses_as_one_loop(ctx: Context) -> None:
    # The slit leads to a hole that reaches out through the outer loop's right wall.
    poking: Points = [
        (0, 0), (20, 0), (20, 10), (14, 10), (14, 6), (24, 6), (24, 14), (14, 14), (14, 10),
        (20, 10), (20, 20), (0, 20),
    ]  # fmt: skip
    result = loop_tree(polygons([poking], ctx), ctx)
    assert codes(result) == ["LOOP_SLIT", "LOOPS_CROSS"]
    assert result.diagnostics[1].location == "loop 0"
    assert result.value is not None
    assert result.value.loops.rows.shape[0] == 0
    assert result.value.crossing_loops.tolist() == [[0, 0], [0, 0]]


@pytest.mark.req("REQ-G2D-241", "REQ-G2D-238")
@pytest.mark.parametrize(
    "drawn",
    [
        # Spec review: the hole drawn the same way round as its outer loop winds twice inside it.
        [(0, 0), (20, 0), (20, 10), (14, 10), (14, 14), (6, 14), (6, 6), (14, 6), (14, 10),
         (20, 10), (20, 20), (0, 20)],
        # A shape beside the loop drawn the other way round winds -1 inside it.
        [(0, 0), (10, 0), (10, 5), (20, 5), (20, 10), (30, 10), (30, 0), (20, 0), (20, 5),
         (10, 5), (10, 10), (0, 10)],
    ],
)  # fmt: skip
def test_pieces_that_wind_twice_or_backwards_still_cross(ctx: Context, drawn: Points) -> None:
    result = loop_tree(polygons([drawn], ctx), ctx)
    assert codes(result) == ["LOOP_SLIT", "LOOPS_CROSS"]
    assert result.diagnostics[1].location == "loop 0"
    assert result.value is not None
    assert result.value.loops.rows.shape[0] == 0
    assert result.value.crossing_loops.tolist() == [[0, 0], [0, 0]]  # at the slit's two ends


@pytest.mark.req("REQ-G2D-241", "REQ-G2D-209")
def test_a_t_shaped_cut_is_spikes_not_a_slit(ctx: Context) -> None:
    # Spec review: the side between the halves holds only two spikes, so it encloses nothing.
    t_cut: Points = [
        (0, 0), (20, 0), (20, 10), (10, 10), (10, 15), (10, 10), (10, 5), (10, 10), (20, 10),
        (20, 20), (0, 20),
    ]  # fmt: skip
    result = loop_tree(polygons([t_cut], ctx), ctx)
    assert "LOOP_SLIT" not in codes(result)
    assert "CLEANUP_SPIKE" in codes(result)
    assert result.value is not None
    assert result.value.depth.tolist() == [0]


@pytest.mark.req("REQ-G2D-241")
def test_a_repeated_vertex_in_a_slit_is_one_slit(ctx: Context) -> None:
    # Spec review: a zero-length row in the way out (a DXF vertex given twice).
    doubled = [*KEYHOLE[:3], (17, 10), (17, 10), *KEYHOLE[3:9], (17, 10), *KEYHOLE[9:]]
    result = loop_tree(polygons([doubled], ctx), ctx)
    assert codes(result) == ["LOOP_SLIT"]
    assert result.value is not None
    assert _pieces(result.value) == _pieces(_tree(polygons([KEYHOLE], ctx), ctx))


@pytest.mark.req("REQ-G2D-241")
def test_two_slits_in_one_loop_give_two_holes(ctx: Context) -> None:
    two: Points = [
        (0, 0), (30, 0), (30, 10), (24, 10), (24, 6), (18, 6), (18, 14), (24, 14), (24, 10),
        (30, 10), (30, 30), (0, 30), (0, 20), (6, 20), (6, 24), (12, 24), (12, 16), (6, 16),
        (6, 20), (0, 20),
    ]  # fmt: skip
    first = loop_tree(polygons([two], ctx), ctx)
    assert codes(first) == ["LOOP_SLIT", "LOOP_SLIT"]
    assert first.value is not None
    assert sorted(first.value.depth.tolist()) == [0, 1, 1]
    turned = loop_tree(polygons([two[7:] + two[:7]], ctx), ctx)
    assert [d.message for d in turned.diagnostics] == [d.message for d in first.diagnostics]


@pytest.mark.req("REQ-G2D-241")
def test_a_slit_of_arcs_is_removed(ctx: Context) -> None:
    rows = np.array(
        [
            [0, 0, 20, 0, NAN, NAN, 0.0],
            [20, 0, 20, 10, NAN, NAN, 0.0],
            [20, 10, 14, 10, 17, 10, -math.pi],  # the way out, below the line y = 10
            [14, 10, 14, 6, NAN, NAN, 0.0],
            [14, 6, 6, 6, NAN, NAN, 0.0],
            [6, 6, 6, 14, NAN, NAN, 0.0],
            [6, 14, 14, 14, NAN, NAN, 0.0],
            [14, 14, 14, 10, NAN, NAN, 0.0],
            [14, 10, 20, 10, 17, 10, math.pi],  # the same arc back
            [20, 10, 20, 20, NAN, NAN, 0.0],
            [20, 20, 0, 20, NAN, NAN, 0.0],
            [0, 20, 0, 0, NAN, NAN, 0.0],
        ]
    )
    built = curve_rows(rows, np.arange(12, dtype=np.int64), np.zeros(1, np.int64), ctx)
    assert built.value is not None
    result = loop_tree(built.value, ctx)
    assert codes(result) == ["LOOP_SLIT"]
    assert result.value is not None
    assert result.value.depth.tolist() == [0, 1]
    assert 2 not in result.value.loops.ids.tolist()
