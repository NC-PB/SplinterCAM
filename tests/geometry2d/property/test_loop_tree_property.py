# SPDX-License-Identifier: Apache-2.0
"""Property tests of the loop tree (research 01, Loop tree, rules 5 and 6; the generator of
test 7): normalised loops wind once around their region; parents, depths and orientations are
those of the nesting, whatever the input order and orientations."""

import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from geometry2d_checks import polygons
from geometry2d_oracles import winding
from splintercam.foundation import Context
from splintercam.geometry2d import LoopTree, loop_tree

Box = tuple[float, float, float, float]


@st.composite
def _nested_boxes(draw: st.DrawFn) -> tuple[list[Box], list[int]]:
    """Up to three columns of boxes, each a chain nested up to four deep with margins of at least
    0.01 mm (more than t_topo); per box its parent's index in the list, -1 for a column's root."""
    boxes: list[Box] = []
    parents: list[int] = []
    for column in range(draw(st.integers(1, 3))):
        x0, y0, x1, y1 = 40.0 * column, 0.0, 40.0 * column + 30.0, 30.0
        for depth in range(draw(st.integers(1, 4))):
            parents.append(len(boxes) - 1 if depth > 0 else -1)
            boxes.append((x0, y0, x1, y1))
            margin = draw(st.floats(0.01, 3.0))
            x0, y0, x1, y1 = x0 + margin, y0 + margin, x1 - margin, y1 - margin
    return boxes, parents


def _tree(boxes: list[Box], order: list[int], flips: list[bool], ctx: Context) -> LoopTree:
    loops: list[list[tuple[float, float]]] = []
    for k in order:
        x0, y0, x1, y1 = boxes[k]
        points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        loops.append(points[::-1] if flips[k] else points)
    result = loop_tree(polygons(loops, ctx), ctx)
    assert result.ok, result.diagnostics
    assert result.value is not None
    return result.value


def _depth(parents: list[int], k: int) -> int:
    return 0 if parents[k] < 0 else 1 + _depth(parents, parents[k])


@pytest.mark.req("REQ-G2D-151", "REQ-G2D-164", "REQ-G2D-174", "REQ-G2D-175")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    nested=_nested_boxes(),
    flips=st.lists(st.booleans(), min_size=12, max_size=12),
    seed=st.integers(0, 2**32 - 1),
    queries=st.lists(
        st.tuples(st.floats(-5.0, 120.0), st.floats(-5.0, 35.0)), min_size=1, max_size=20
    ),
)
def test_the_tree_is_the_nesting_in_any_order(
    ctx: Context,
    nested: tuple[list[Box], list[int]],
    flips: list[bool],
    seed: int,
    queries: list[tuple[float, float]],
) -> None:
    boxes, true_parents = nested
    order = list(range(len(boxes)))
    random.Random(seed).shuffle(order)
    tree = _tree(boxes, order, flips, ctx)
    # Parents and depths of the nesting, mapped through the input order (REQ-G2D-164, 174).
    position = {box: k for k, box in enumerate(order)}
    expected = [-1 if true_parents[b] < 0 else position[true_parents[b]] for b in order]
    assert tree.parent.tolist() == expected
    assert tree.depth.tolist() == [_depth(true_parents, b) for b in order]
    # The same tree from another order and other orientations, loop for loop.
    other = _tree(boxes, list(range(len(boxes))), [not f for f in flips], ctx)
    assert [other.depth[b] for b in order] == tree.depth.tolist()
    # Normalised: even depth CCW, odd CW, and a winding of 1 inside the region (REQ-G2D-151).
    rows, starts = tree.loops.rows, tree.loops.row_starts.tolist()
    ends = [*starts[1:], rows.shape[0]]
    loops = [
        [(float(r[0]), float(r[1])) for r in rows[a:b]] for a, b in zip(starts, ends, strict=True)
    ]
    for depth, loop in zip(tree.depth.tolist(), loops, strict=True):
        area = sum(
            p[0] * q[1] - q[0] * p[1] for p, q in zip(loop, loop[1:] + loop[:1], strict=True)
        )
        assert (area > 0) == (depth % 2 == 0)
    t_topo = ctx.tolerances.topology_tol_mm
    for q in queries:
        near = any(
            (min(abs(q[0] - x0), abs(q[0] - x1)) <= t_topo and y0 - t_topo <= q[1] <= y1 + t_topo)
            or (
                min(abs(q[1] - y0), abs(q[1] - y1)) <= t_topo and x0 - t_topo <= q[0] <= x1 + t_topo
            )
            for x0, y0, x1, y1 in boxes
        )
        if near:
            continue
        windings = [winding(q, loop) for loop in loops]
        assert None not in windings  # away from every boundary
        inside = sum(x0 < q[0] < x1 and y0 < q[1] < y1 for x0, y0, x1, y1 in boxes)
        assert sum(w for w in windings if w is not None) == inside % 2
