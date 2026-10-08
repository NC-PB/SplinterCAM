# SPDX-License-Identifier: Apache-2.0
"""Unit tests for a loop's crossings with itself (research 01, Loop tree, rule 4; REQ-G2D-238)."""

import math

import numpy as np
import pytest

from geometry2d_checks import codes, polygons
from splintercam.foundation import Context
from splintercam.geometry2d import _selfcross as selfcross
from splintercam.geometry2d import curve_rows, loop_tree
from splintercam.geometry2d._contain import Nesting
from splintercam.geometry2d._screen import screen_loops

Points = list[tuple[float, float]]
NAN = math.nan

CROSSING: dict[str, Points] = {
    "bow-tie, area 0": [(0, 0), (10, 0), (0, 10), (10, 10)],
    "figure eight, unequal lobes": [(0, 0), (10, -5), (10, 5), (0, 0), (-1, -1), (-1, 1)],
    "loop run round twice": [
        (0, 0),
        (10, 0),
        (10, 10),
        (0, 10),
        (0, 1),
        (9, 1),
        (9, 9),
        (1, 9),
        (1, 0.5),
        (0, 0.5),
    ],
    "one CW petal of three": [
        (0, 0),
        (2, -1),
        (2, 1),
        (0, 0),
        (-2, 1),
        (-2, -1),
        (0, 0),
        (-1, 2),
        (1, 2),
    ],
    "fishtail with legs of 0.0015 mm": [(10, 0), (10, 10.0015), (10.0015, 10), (0, 10), (0, 0)],
    # A curl of 1e-4 mm runs a stretch twice: counted as crossing, provisionally (DEC-G2D-033).
    "curl of 1e-4 mm": [
        (0, 0),
        (5, 0),
        (5, 1e-4),
        (4.9999, 1e-4),
        (4.9999, 0),
        (10, 0),
        (10, 10),
        (0, 10),
    ],
}
TOUCHING: dict[str, Points] = {
    "pinch with a lens": [
        (0, 0),
        (4, 0),
        (5, 2.00005),
        (6, 0),
        (10, 0),
        (10, 4),
        (6, 4),
        (5, 1.99995),
        (4, 4),
        (0, 4),
    ],
    "fishtail with legs of 1e-4 mm": [(10, 0), (10, 10.0001), (10.0001, 10), (0, 10), (0, 0)],
    "pinched annulus": [(0, 0), (10, 0), (10, 10), (5, 10), (7, 8), (3, 8), (5, 10), (0, 10)],
    "three CCW petals through one point": [
        (0, 0),
        (2, -1),
        (2, 1),
        (0, 0),
        (-2, 1),
        (-2, -1),
        (0, 0),
        (1, 2),
        (-1, 2),
    ],
}


@pytest.mark.req("REQ-G2D-238", "REQ-G2D-160", "REQ-G2D-161")
@pytest.mark.parametrize("name", list(CROSSING))
def test_a_loop_crossing_itself_is_reported(ctx: Context, name: str) -> None:
    result = screen_loops(polygons([CROSSING[name]], ctx), ctx)
    assert result.value is not None
    assert result.value.kept.size == 0
    assert codes(result) == ["LOOPS_CROSS"]
    assert result.diagnostics[0].location == "loop 0"
    assert result.value.crossing_points.shape[0] >= 1  # a stretch run twice: its ends
    assert (result.value.crossing_loops == 0).all()  # the pair (0, 0)


# Spec review of 4c: lobes of area +15 and -20 whose ends at the node sort as in, out, out, in
# from +x; pairing them twice joined both lobes into one cycle, a touching loop.
EIGHT: Points = [(10, 0), (0, 0), (0, -3), (5, -3), (5, 4), (10, 4)]


@pytest.mark.req("REQ-G2D-238", "REQ-G2D-160")
@pytest.mark.parametrize("quarter", range(4))
@pytest.mark.parametrize("backward", [False, True])
def test_a_figure_eight_crosses_from_every_start_and_turn(
    ctx: Context, quarter: int, backward: bool
) -> None:
    c, s = [(1, 0), (0, 1), (-1, 0), (0, -1)][quarter]
    turned = [(c * x - s * y, s * x + c * y) for x, y in EIGHT]
    for k in range(len(turned)):
        loop = turned[k:] + turned[:k]
        result = screen_loops(polygons([loop[::-1] if backward else loop], ctx), ctx)
        assert codes(result) == ["LOOPS_CROSS"], k
        assert result.value is not None
        assert result.value.crossing_points.tolist() == [[5.0 * c, 5.0 * s]]


@pytest.mark.req("REQ-G2D-238", "REQ-G2D-162")
def test_a_wall_running_a_stretch_twice_leaves_no_tree(ctx: Context) -> None:
    # Spec review of 4c: [50, 60] x {0} is run twice in one direction; the island inside kept a
    # tree of its own when the stretch gave no crossing points.
    wall: Points = [(0, 0), (60, 0), (60, -1), (50, -1), (50, 0), (100, 0), (100, 100), (0, 100)]
    island = [(10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)]
    result = loop_tree(polygons([wall, island], ctx), ctx)
    assert codes(result) == ["LOOPS_CROSS"]
    assert result.value is not None
    assert result.value.loops.rows.shape[0] == 0
    assert result.value.crossing_points.tolist() == [[50.0, 0.0], [60.0, 0.0]]


@pytest.mark.req("REQ-G2D-238", "REQ-G2D-163")
@pytest.mark.parametrize("name", list(TOUCHING))
def test_a_loop_touching_itself_is_kept(ctx: Context, name: str) -> None:
    result = screen_loops(polygons([TOUCHING[name]], ctx), ctx)
    assert result.value is not None
    assert result.value.kept.tolist() == [0]
    assert codes(result) == []
    assert result.value.areas[0] > 0  # the sign of its depth-0 cycles: these are CCW


@pytest.mark.req("REQ-G2D-238", "REQ-G2D-162")
def test_a_bow_tie_wall_leaves_no_tree_for_the_island_inside(ctx: Context) -> None:
    # Spec review: area tests first would drop the bow-tie as degenerate, and its island would
    # become a root; reported as crossing, the tree holds no loops.
    island = [(4.0, 1.0), (6.0, 1.0), (6.0, 2.0), (4.0, 2.0)]
    result = loop_tree(polygons([CROSSING["bow-tie, area 0"], island], ctx), ctx)
    assert not result.ok
    assert codes(result) == ["LOOPS_CROSS"]
    assert result.value is not None
    assert result.value.loops.rows.shape[0] == 0
    assert result.value.crossing_points.tolist() == [[5.0, 5.0]]
    assert result.value.crossing_loops.tolist() == [[0, 0]]


@pytest.mark.req("REQ-G2D-238")
def test_a_circle_of_two_full_rows_on_one_circle_crosses(ctx: Context) -> None:
    row = [5.0, 0.0, 5.0, 0.0, 0.0, 0.0, math.tau]
    built = curve_rows(
        np.array([row, row]), np.arange(2, dtype=np.int64), np.zeros(1, np.int64), ctx
    )
    assert built.value is not None, built.diagnostics
    result = screen_loops(built.value, ctx)
    assert codes(result) == ["LOOPS_CROSS"]


@pytest.mark.req("REQ-G2D-236")
def test_crossing_points_sort_by_pair_then_x_then_y(ctx: Context) -> None:
    squares: list[Points] = [
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        [(5, 5), (15, 5), (15, 15), (5, 15)],
    ]
    result = screen_loops(polygons([CROSSING["bow-tie, area 0"], *squares], ctx), ctx)
    assert result.value is not None
    assert result.value.crossing_loops.tolist() == [[0, 0], [1, 2], [1, 2]]
    assert codes(result) == ["LOOPS_CROSS", "LOOPS_CROSS"]


@pytest.mark.req("REQ-G2D-238", "REQ-G2D-034")
def test_a_refused_fallback_for_the_cycles_is_reported_as_refused(
    ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Spec review of 4c: the refusal was reported as LOOPS_CROSS, "crosses itself".
    def refusing(polylines: list[object], *_: object) -> Nesting:
        k = len(polylines)
        return Nesting([-1] * k, [0] * k, [], [(0, 1, "REGION_TOO_LARGE")])

    monkeypatch.setattr(selfcross, "nest", refusing)
    island = [(4.0, 1.0), (6.0, 1.0), (6.0, 2.0), (4.0, 2.0)]
    name = next(iter(TOUCHING))
    result = loop_tree(polygons([TOUCHING[name], island], ctx), ctx)
    assert codes(result) == ["REGION_TOO_LARGE"]
    assert result.diagnostics[0].location == "loop 0"
    assert result.value is not None
    assert result.value.loops.rows.shape[0] == 0  # no tree


@pytest.mark.req("REQ-G2D-238")
def test_a_zero_width_slit_crosses_for_now(ctx: Context) -> None:
    # A keyhole drawn as one loop: the slit [6, 10] x {5} is run out to the square hole and back
    # (DEC-G2D-033, provisional; asked of Peter in plan 0004).
    loop: Points = [(0, 0), (10, 0), (10, 5), (6, 5), (6, 6), (4, 6), (4, 4), (6, 4), (6, 5)]
    loop += [(10, 5), (10, 10), (0, 10)]
    result = screen_loops(polygons([loop], ctx), ctx)
    assert codes(result) == ["LOOPS_CROSS"]
    assert result.value is not None
    assert result.value.crossing_points.shape[0] >= 1
