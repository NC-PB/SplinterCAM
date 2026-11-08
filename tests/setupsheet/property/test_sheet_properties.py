# SPDX-License-Identifier: Apache-2.0
"""Property tests of the setup sheet's invariants (src/splintercam/setupsheet/SPEC.md,
Invariants): the reach holds the tool below h_c (REQ-SHT-012), the gap is the clearance to the
stock box (REQ-SHT-011)."""

import math

import numpy as np
from hypothesis import assume, given
from hypothesis import strategies as st

from cl_strategies import H_C, HEADER, NAN, PLUNGE, Move, columns, line, operations, rapid
from model_jobs import make_context
from setupsheet_cases import FILES, STOCK, golden_job, job_operation, part
from splintercam.cl import MoveKind, Role, make_cl_data, make_operation
from splintercam.model import FlatEndMill, StockBox
from splintercam.setupsheet import Box3, SetupSheet, Side, make_setup_sheet

_LOW_STOCK = StockBox((-1e3, -1e3, -200.0), (1e3, 1e3, -100.0))  # below every generated level
_radius = st.integers(1, 40).map(lambda k: k * 0.25)


def _sheet_of(moves: list[Move], radius: float, stock: StockBox) -> SetupSheet:
    ctx = make_context()
    data = make_cl_data(1, (make_operation(HEADER, columns(moves), ctx),), ctx)
    job = golden_job((job_operation(HEADER.name),), (FlatEndMill(1, 2.0 * radius, 30.0),), stock)
    return make_setup_sheet(job, data, part(ctx), FILES, ctx)


def _inside(box: Box3, x: float, y: float, radius: float, slack: float = 0.0) -> bool:
    """(x, y) grown by R inside `box`; `slack` 0 for move ends (exact), else one ulp of the box
    (the SPEC's allowance for `row_boxes`' C ± r) plus the arc sample's own rounding."""
    lo_x, lo_y = box.min_mm[0], box.min_mm[1]
    hi_x, hi_y = box.max_mm[0], box.max_mm[1]
    if slack:
        lo_x, lo_y = (
            math.nextafter(lo_x, -math.inf) - slack,
            math.nextafter(lo_y, -math.inf) - slack,
        )
        hi_x, hi_y = math.nextafter(hi_x, math.inf) + slack, math.nextafter(hi_y, math.inf) + slack
    return lo_x <= x - radius and x + radius <= hi_x and lo_y <= y - radius and y + radius <= hi_y


@given(operations(with_arc=True), _radius)
def test_the_reach_holds_the_tool_below_h_c(moves: list[Move], radius: float) -> None:
    reach = _sheet_of(moves, radius, _LOW_STOCK).operations[0].reach
    assert reach is not None  # every generated operation cuts below h_r
    lowest = min(m.end[2] for m in moves)
    assert (reach.min_mm[2], reach.max_mm[2]) == (lowest, H_C)
    for index in range(2, len(moves)):
        move, start = moves[index], moves[index - 1].end
        if not (move.end[2] < H_C or start[2] < H_C):
            continue
        for x, y in (start[:2], move.end[:2]):
            assert _inside(reach, x, y, radius), (index, x, y)
        if move.kind is MoveKind.ARC:
            cx, cy = move.centre
            r = math.sqrt((start[0] - cx) ** 2 + (start[1] - cy) ** 2)
            begin = math.atan2(start[1] - cy, start[0] - cx)
            # The sample c + r·(cos, sin) is itself off the arc by a few ulps of |c| + r.
            sample_error = 8.0 * math.ulp(abs(cx) + abs(cy) + r)
            for t in np.linspace(0.0, move.sweep, 64)[1:-1]:  # the ends are checked exactly
                x, y = cx + r * math.cos(begin + t), cy + r * math.sin(begin + t)
                assert _inside(reach, x, y, radius, sample_error), (index, x, y)


_GRID = 2.0**-6
_coord = st.integers(-60 * 64, 170 * 64).map(lambda k: k * _GRID)


def _clearance(x: float, y: float) -> float:
    lo, hi = STOCK.min_mm, STOCK.max_mm
    dx, dy = max(lo[0] - x, 0.0, x - hi[0]), max(lo[1] - y, 0.0, y - hi[1])
    return math.sqrt(dx * dx + dy * dy)


@given(_coord, _coord, _radius)
def test_the_gap_is_the_clearance_to_the_stock_box(x: float, y: float, radius: float) -> None:
    lo, hi = STOCK.min_mm, STOCK.max_mm
    dx, dy = max(lo[0] - x, 0.0, x - hi[0]), max(lo[1] - y, 0.0, y - hi[1])
    assume(dx * dx + dy * dy > radius * radius)  # REQ-TP-012's expression
    moves = [rapid(NAN, NAN, H_C, H_C), rapid(x, y, H_C, H_C), rapid(x, y, 3.0, 3.0),
             line(x, y, -1.0, Role.APPROACH, PLUNGE), line(x + 1.0, y, -1.0),
             rapid(x + 1.0, y, H_C, H_C)]  # fmt: skip
    (point,) = _sheet_of(moves, radius, STOCK).operations[0].approach_points
    assert point.gap_mm is not None
    assert point.centre_distance_mm is not None
    assert math.isclose(point.centre_distance_mm, _clearance(x, y), abs_tol=1e-12)
    # Moved toward the box by the gap, the point lies R from the box.
    qx, qy = min(max(x, lo[0]), hi[0]), min(max(y, lo[1]), hi[1])
    d = math.sqrt((qx - x) ** 2 + (qy - y) ** 2)
    moved = (x + point.gap_mm * (qx - x) / d, y + point.gap_mm * (qy - y) / d)
    assert abs(_clearance(*moved) - radius) <= 1e-9
    outside = (x < lo[0], x > hi[0], y < lo[1], y > hi[1])
    sides = (Side.MINUS_X, Side.PLUS_X, Side.MINUS_Y, Side.PLUS_Y)
    expected = [s for s, out in zip(sides, outside, strict=True) if out]
    assert point.side is (expected[0] if len(expected) == 1 else Side.CORNER)
