# SPDX-License-Identifier: Apache-2.0
"""Research 02's test 16: an island touching the pocket wall, shrunk by 3, never comes closer than
3 to either loop (offset2d SPEC, Example parts). The golden case `pocket-island-touching-wall`
follows with the pocket strategy and the golden tools (Peter, 2026-10-10); this is its check on
offset2d's own output."""

import math

import numpy as np
import pytest

from geometry2d_checks import codes, reversed_loop
from offset2d_oracles import (
    DistanceBand,
    distance_to_curves,
    in_offset,
    polygon_rows,
    sample_outside_band,
    true_curve_band_mm,
)
from offset2d_strategies import circle, rounded_box, to_curve_rows
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows, PointLocation, RegionKind, point_in_region
from splintercam.offset2d import EdgeClass, SourceClasses, offset_region

T_MM = 3.0  # research 02, test 16
ISLAND_R_MM = 8.0
N_POINTS = 10_000  # research 02, test 9's sample, at the known answer
# The distance oracle's error, 64·ε·S (`offset2d_oracles`), below 1e-12 mm for S = 60 mm here;
# 1e-9 mm bounds it with room and stays five orders below u.
ORACLE_SLACK_MM = 1e-9


def _loops(
    ctx: Context, corner_mm: float, island_start: float
) -> tuple[CurveRows, tuple[CurveRows, CurveRows]]:
    """The pocket [0, 60] x [0, 40] and a circular island of radius 8 touching its top side at
    (30, 40), each as its own curve rows (row IDs 100, ... for the wall, then the island's)."""
    wall = rounded_box(0.0, 0.0, 60.0, 40.0, corner_mm)
    island = reversed_loop(circle(30.0, 40.0 - ISLAND_R_MM, ISLAND_R_MM, island_start, 2))
    both = to_curve_rows([wall, island], ctx)
    first_island_row = len(wall)
    rows = np.asarray(both.rows)
    split = (
        CurveRows(rows[:first_island_row], both.ids[:first_island_row], np.array([0])),
        CurveRows(rows[first_island_row:], both.ids[first_island_row:], np.array([0])),
    )
    return both, split


@pytest.mark.req("REQ-OFF-020", "REQ-OFF-025")
@pytest.mark.parametrize("corner_mm", [0.0, 5.0])
@pytest.mark.parametrize("island_start", [math.pi / 2, 0.3])  # a vertex at the touch point, or not
def test_an_island_touching_the_wall_keeps_3_from_either_loop(
    ctx: Context, corner_mm: float, island_start: float
) -> None:
    both, (wall, island) = _loops(ctx, corner_mm, island_start)
    ids = np.unique(both.ids)
    classes = SourceClasses(ids, np.full(ids.size, int(EdgeClass.MATERIAL), dtype=np.int8))
    result = offset_region(both, RegionKind.AIR, T_MM, classes, ctx)
    assert result.value is not None, codes(result)
    assert codes(result) == []
    region = result.value
    # The island grown by 3 meets the wall grown by 3: one loop, no hole, round the island.
    assert region.loop_starts.tolist() == [0]
    rows = polygon_rows(region.points, region.loop_starts)
    probes = np.concatenate([region.points, (rows.rows[:, 0:2] + rows.rows[:, 2:4]) / 2.0])
    top = T_MM + true_curve_band_mm(ctx.tolerances)
    for loop in (wall, island):
        d = distance_to_curves(probes, loop)
        assert d.min() >= T_MM - ORACLE_SLACK_MM
    assert distance_to_curves(probes, both).max() <= top
    # Research 02's definition at 10^4 points outside the band (test 9's oracle).
    band = DistanceBand(T_MM, true_curve_band_mm(ctx.tolerances))
    points = sample_outside_band(both, band, (-1.0, -1.0, 61.0, 41.0), N_POINTS, 16)
    expected = in_offset(points, both, RegionKind.AIR, T_MM)
    located = point_in_region(points, rows, ctx)
    assert np.array_equal(located == PointLocation.IN, expected)
