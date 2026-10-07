# SPDX-License-Identifier: Apache-2.0
"""Property test: normalised loops wind once around their region (research 01, Loop tree, rule 6;
the generator of test 7)."""

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from geometry2d_checks import polygons
from geometry2d_oracles import winding
from splintercam.foundation import Context
from splintercam.geometry2d import loop_tree

Box = tuple[float, float, float, float]


@st.composite
def _nested_boxes(draw: st.DrawFn) -> list[Box]:
    """Up to three columns of boxes, each column a chain nested up to four deep with margins of at
    least 0.01 mm (more than t_topo), so no two boxes touch or cross."""
    boxes: list[Box] = []
    for column in range(draw(st.integers(1, 3))):
        x0, y0, x1, y1 = 40.0 * column, 0.0, 40.0 * column + 30.0, 30.0
        for _ in range(draw(st.integers(1, 4))):
            boxes.append((x0, y0, x1, y1))
            margin = draw(st.floats(0.01, 3.0))
            x0, y0, x1, y1 = x0 + margin, y0 + margin, x1 - margin, y1 - margin
    return boxes


@pytest.mark.req("REQ-G2D-151", "REQ-G2D-164", "REQ-G2D-174", "REQ-G2D-175")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    boxes=_nested_boxes(),
    flips=st.lists(st.booleans(), min_size=12, max_size=12),
    order=st.randoms(use_true_random=False),
    queries=st.lists(
        st.tuples(st.floats(-5.0, 120.0), st.floats(-5.0, 35.0)), min_size=1, max_size=20
    ),
)
def test_normalised_loops_wind_once_around_their_region(
    ctx: Context,
    boxes: list[Box],
    flips: list[bool],
    order: object,
    queries: list[tuple[float, float]],
) -> None:
    import random

    assert isinstance(order, random.Random)
    shuffled = boxes[:]
    order.shuffle(shuffled)
    loops: list[list[tuple[float, float]]] = []
    for (x0, y0, x1, y1), flip in zip(shuffled, flips, strict=False):
        points = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        loops.append(points[::-1] if flip else points)
    result = loop_tree(polygons(loops, ctx), ctx)
    assert result.ok, result.diagnostics
    tree = result.value
    assert tree is not None
    assert sorted(tree.input_index.tolist()) == list(range(len(loops)))
    rows, starts = tree.loops.rows, tree.loops.row_starts.tolist()
    ends = [*starts[1:], rows.shape[0]]
    normalised = [
        [(float(r[0]), float(r[1])) for r in rows[a:b]] for a, b in zip(starts, ends, strict=True)
    ]
    t_topo = ctx.tolerances.topology_tol_mm
    for q in queries:
        inside = sum(x0 < q[0] < x1 and y0 < q[1] < y1 for x0, y0, x1, y1 in boxes)
        near = any(
            (min(abs(q[0] - x0), abs(q[0] - x1)) <= t_topo and y0 - t_topo <= q[1] <= y1 + t_topo)
            or (
                min(abs(q[1] - y0), abs(q[1] - y1)) <= t_topo and x0 - t_topo <= q[0] <= x1 + t_topo
            )
            for x0, y0, x1, y1 in boxes
        )
        if near:
            continue
        total = sum(winding(q, loop) or 0 for loop in normalised)
        assert total == inside % 2  # 1 inside the region, 0 outside (REQ-G2D-151)
    for depth, loop in zip(tree.depth.tolist(), normalised, strict=True):
        area = sum(
            p[0] * q[1] - q[0] * p[1] for p, q in zip(loop, loop[1:] + loop[:1], strict=True)
        )
        assert (area > 0) == (depth % 2 == 0)  # even depth CCW, odd CW
