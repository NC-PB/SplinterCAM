# SPDX-License-Identifier: Apache-2.0
"""Known answers for `dense_loops` (`tests/support/offset2d_oracles.py`), the densifier that hands
the true curves to GEOS in test 20: its vertices lie on the true curves, and the polygon and the
true curves lie within 2s of each other both ways (s from the chords, up to about 1.56·s where an
arc's end E within s of P1 is left out; DEC-OFF-022).

Like `test_offset2d_oracles.py`, these test the test support, so they carry no requirement marker.
"""

import math

import numpy as np
import pytest

from offset2d_oracles import dense_loops, distance_to_curves, polygon_rows
from offset2d_strategies import circle, rounded_box
from splintercam.geometry2d import CurveRows

NAN = math.nan
S_MM = 1e-4  # the sagitta test 20 uses: u
FLOAT_MM = 1e-9  # float rounding of a vertex placed on a circle of radius up to 30 mm


def _rows(loops: list[list[list[float]]]) -> CurveRows:
    """Unchecked curve rows (the densifier reads them as the oracles do), IDs 0, 1, ..."""
    rows = np.array([row for loop in loops for row in loop], dtype=np.float64)
    starts = np.cumsum([0] + [len(loop) for loop in loops[:-1]]).astype(np.int64)
    return CurveRows(rows, np.arange(rows.shape[0], dtype=np.int64), starts)


def _quarter_to(p1: tuple[float, float]) -> CurveRows:
    """A quarter of the circle of radius 10 from (10, 0) to the ray through `p1`, then along it
    to `p1` (geometry2d's radial connector), closed by lines through the centre."""
    return _rows(
        [[[10.0, 0.0, *p1, 0.0, 0.0, math.pi / 2],
          [*p1, 0.0, 0.0, NAN, NAN, 0.0],
          [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0]]]
    )  # fmt: skip


def _two_way(loops: CurveRows) -> tuple[float, float]:
    """The largest distance from the densified polygon to the true curves (vertices and the
    points of a finer densification of the polygon itself), and back."""
    coarse = dense_loops(loops, S_MM)
    starts = np.cumsum([0] + [p.shape[0] for p in coarse[:-1]])
    polygon = polygon_rows(np.concatenate(coarse), starts)
    on_polygon = np.concatenate(dense_loops(polygon, S_MM / 100.0))
    fine = np.concatenate(dense_loops(loops, S_MM / 100.0))  # vertices on the true curves
    return float(distance_to_curves(on_polygon, loops).max()), float(
        distance_to_curves(fine, polygon).max()
    )


@pytest.mark.parametrize(
    "loops",
    [
        [circle(0.0, 0.0, 30.0, 0.3, 1)],
        [circle(5.0, -2.0, 2.0, 1.0, 3)],
        [rounded_box(0.0, 0.0, 60.0, 40.0, 5.0), circle(20.0, 20.0, 8.0, 0.0, 2)],
    ],
)
def test_vertices_lie_on_the_true_curves_and_both_lie_within_s(
    loops: list[list[list[float]]],
) -> None:
    rows = _rows(loops)
    vertices = np.concatenate(dense_loops(rows, S_MM))
    assert distance_to_curves(vertices, rows).max() <= FLOAT_MM
    to_curves, to_polygon = _two_way(rows)
    assert to_curves <= S_MM + FLOAT_MM
    assert to_polygon <= S_MM + FLOAT_MM


def test_a_full_circle_closes_without_repeating_its_start() -> None:
    (ring,) = dense_loops(_rows([circle(0.0, 0.0, 10.0, 0.0, 1)]), S_MM)
    assert ring.shape[0] > 4
    gaps = np.hypot(*(np.roll(ring, -1, axis=0) - ring).T)
    assert gaps.min() > S_MM  # no duplicate vertex for GEOS's noding
    assert np.allclose(ring[0], [10.0, 0.0], rtol=0.0, atol=0.0)


@pytest.mark.parametrize(("connector_mm", "kept"), [(0.9 * S_MM, False), (1.1 * S_MM, True)])
def test_an_arc_end_within_s_of_p1_is_left_out_and_the_bound_stays_under_2s(
    connector_mm: float, kept: bool
) -> None:
    rows = _quarter_to((0.0, 10.0 + connector_mm))
    (ring,) = dense_loops(rows, S_MM)
    e = np.array([0.0, 10.0])
    assert bool(np.any(np.hypot(*(ring - e).T) <= FLOAT_MM)) is kept
    to_curves, to_polygon = _two_way(rows)
    assert to_curves <= 2.0 * S_MM
    assert to_polygon <= 2.0 * S_MM
