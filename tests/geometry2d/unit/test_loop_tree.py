# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the loop tree: parents, depths, normalisation (research 01, Loop tree, rules 5
and 6; tests 7 and 24)."""

import itertools

import numpy as np
import pytest

from geometry2d_checks import codes, polygons
from splintercam.foundation import Context
from splintercam.geometry2d import LoopTree, loop_tree, signed_area
from splintercam.geometry2d._tree import Containment, both_ways

Points = list[tuple[float, float]]


def _box(x0: float, y0: float, x1: float, y1: float) -> Points:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _tree(loops: list[Points], ctx: Context) -> LoopTree:
    result = loop_tree(polygons(loops, ctx), ctx)
    assert result.ok, result.diagnostics
    assert result.value is not None
    return result.value


def _signs(tree: LoopTree, ctx: Context) -> list[int]:
    rows, ids, starts = tree.loops.rows, tree.loops.ids, tree.loops.row_starts
    ends = np.append(starts[1:], rows.shape[0])
    signs: list[int] = []
    for a, b in zip(starts.tolist(), ends.tolist(), strict=True):
        from splintercam.geometry2d import CurveRows

        area = signed_area(CurveRows(rows[a:b], ids[a:b], np.zeros(1, np.int64)), ctx).value
        assert area is not None
        signs.append(1 if area > 0 else -1)
    return signs


NESTED = [_box(0, 0, 30, 30), _box(5, 5, 25, 25), _box(10, 10, 20, 20)]


@pytest.mark.req("REQ-G2D-164", "REQ-G2D-174")
def test_three_nested_squares_of_research_test_7(ctx: Context) -> None:
    tree = _tree(NESTED, ctx)
    assert tree.parent.tolist() == [-1, 0, 1]
    assert tree.depth.tolist() == [0, 1, 2]
    assert tree.input_index.tolist() == [0, 1, 2]


@pytest.mark.req("REQ-G2D-164", "REQ-G2D-174")
def test_the_tree_does_not_depend_on_input_order(ctx: Context) -> None:
    tree = _tree([NESTED[2], NESTED[0], NESTED[1]], ctx)
    assert tree.input_index.tolist() == [0, 1, 2]
    assert tree.parent.tolist() == [2, -1, 1]
    assert tree.depth.tolist() == [2, 0, 1]


@pytest.mark.req("REQ-G2D-164", "REQ-G2D-174")
def test_two_regions_side_by_side(ctx: Context) -> None:
    tree = _tree([_box(0, 0, 10, 10), _box(20, 0, 30, 10)], ctx)
    assert tree.parent.tolist() == [-1, -1]
    assert tree.depth.tolist() == [0, 0]


@pytest.mark.req("REQ-G2D-167", "REQ-G2D-168")
@pytest.mark.parametrize(
    "inner",
    [
        [(0, 0), (10, 0), (10, 10)],  # its probe is the midpoint of its hypotenuse
        [(0, 0), (2, 0), (2, 5), (2.1, 5), (2.1, 0), (10, 0), (10, 10), (0, 10)],  # 0.1 mm notch
    ],
)
def test_a_loop_touching_its_parent_is_its_child(ctx: Context, inner: Points) -> None:
    tree = _tree([_box(0, 0, 10, 10), inner], ctx)
    assert tree.parent.tolist() == [-1, 0]


@pytest.mark.req("REQ-G2D-165", "REQ-G2D-166", "REQ-G2D-170")
@pytest.mark.parametrize("swap", [False, True])
@pytest.mark.parametrize(
    "other",
    [
        _box(0, 0, 10.001, 10),  # areas 0.01 mm² apart: the rectangle is the parent
        [(0, 0), (2, 0), (2, 5), (2.002, 5), (2.002, 0), (10, 0), (10, 10), (0, 10)],  # child
    ],
)
def test_close_areas_of_research_test_24(ctx: Context, other: Points, swap: bool) -> None:
    square = _box(0, 0, 10, 10)
    order = [other, square] if swap else [square, other]
    tree = _tree(order, ctx)
    square_index, other_index = (1, 0) if swap else (0, 1)
    is_rectangle = len(other) == 4
    child, parent = (square_index, other_index) if is_rectangle else (other_index, square_index)
    assert tree.parent[child] == parent
    assert tree.parent[parent] == -1


@pytest.mark.req("REQ-G2D-175")
@pytest.mark.parametrize("flips", list(itertools.product([False, True], repeat=3)))
def test_orientation_is_normalised(ctx: Context, flips: tuple[bool, bool, bool]) -> None:
    given = [box[::-1] if flip else box for box, flip in zip(NESTED, flips, strict=True)]
    tree = _tree(given, ctx)
    assert _signs(tree, ctx) == [1, -1, 1]


@pytest.mark.req("REQ-G2D-175")
def test_normalising_reverses_the_rows_and_their_ids(ctx: Context) -> None:
    tree = _tree(NESTED, ctx)  # the hole given CCW, as _box makes it
    start, end = int(tree.loops.row_starts[1]), int(tree.loops.row_starts[2])
    assert tree.loops.ids[start:end].tolist() == [107, 106, 105, 104]
    rows = tree.loops.rows[start:end]
    assert (rows[1:, 0:2] == rows[:-1, 2:4]).all()  # still continuous


@pytest.mark.req("REQ-G2D-162", "REQ-G2D-161")
def test_crossing_loops_leave_no_loops(ctx: Context) -> None:
    result = loop_tree(
        polygons([_box(0, 0, 10, 10), _box(5, 5, 15, 15), _box(30, 0, 40, 10)], ctx), ctx
    )
    assert not result.ok
    assert codes(result) == ["LOOPS_CROSS"]
    tree = result.value
    assert tree is not None
    assert tree.loops.rows.shape[0] == 0
    assert tree.parent.size == 0
    assert tree.crossing_points.tolist() == [[5.0, 10.0], [10.0, 5.0]]
    assert tree.crossing_loops.tolist() == [[0, 1], [0, 1]]


@pytest.mark.req("REQ-G2D-155", "REQ-G2D-168")
def test_a_spike_loop_starting_at_its_tip_is_the_squares_child(ctx: Context) -> None:
    tip_first = [(15.0, 25.0), (15.0, 10.0), (5.0, 10.0), (5.0, 5.0), (15.0, 5.0), (15.0, 10.0)]
    tree = _tree([_box(0, 0, 20, 20), tip_first], ctx)
    assert tree.parent.tolist() == [-1, 0]


@pytest.mark.req("REQ-G2D-170", "REQ-G2D-173")
def test_the_both_ways_decision() -> None:
    probe_in, probe_out = Containment(True, True), Containment(False, True)
    no_probe = Containment(False, False)
    assert both_ways(probe_in, probe_out) == "a in b"
    assert both_ways(probe_out, probe_in) == "b in a"
    assert both_ways(probe_in, no_probe) == "a in b"  # the probe stands (REQ-G2D-170)
    assert both_ways(no_probe, probe_in) == "b in a"
    assert both_ways(probe_in, probe_in) == "cross"  # REQ-G2D-173
    assert both_ways(no_probe, no_probe) == "apart"  # provisional until the fallback, DEC-G2D-032
