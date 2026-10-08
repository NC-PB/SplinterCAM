# SPDX-License-Identifier: Apache-2.0
"""Unit tests for a loop's crossings with itself (research 01, Loop tree, rule 4; REQ-G2D-238)."""

import math

import numpy as np
import pytest

from geometry2d_checks import codes, polygons
from splintercam.foundation import Context
from splintercam.geometry2d import curve_rows, loop_tree
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
    if name != "curl of 1e-4 mm":
        assert result.value.crossing_points.shape[0] >= 1
        assert (result.value.crossing_loops == 0).all()  # the pair (0, 0)


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
