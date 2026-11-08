# SPDX-License-Identifier: Apache-2.0
"""The golden job's sheet as values (src/splintercam/setupsheet/SPEC.md, Example parts):
REQ-SHT-005 to 016."""

import math
from dataclasses import replace

import pytest

from setupsheet_cases import FILES, STOCK, P, golden_job, part, record
from splintercam.foundation import Context
from splintercam.model import StockBox
from splintercam.setupsheet import ApproachPoint, Box3, SetupSheet, Side, make_setup_sheet


def _sheet(ctx: Context, stock: StockBox = STOCK) -> SetupSheet:
    return make_setup_sheet(golden_job(stock=stock), record(ctx), part(ctx), FILES, ctx)


@pytest.mark.req("REQ-SHT-005")
def test_the_part_box_is_the_contours(ctx: Context) -> None:
    assert _sheet(ctx).part_box_xy_mm == (0.0, 0.0, 100.0, 60.0)


@pytest.mark.req("REQ-SHT-006", "REQ-SHT-007")
def test_work_offset_and_stock_box(ctx: Context) -> None:
    sheet = _sheet(ctx)
    assert sheet.work_offset == 1
    assert sheet.stock == Box3((-5.0, -5.0, -20.0), (105.0, 65.0, 0.0))


@pytest.mark.req("REQ-SHT-008")
def test_one_tool_at_the_tip(ctx: Context) -> None:
    (tool,) = _sheet(ctx).tools
    assert (tool.number, tool.diameter_mm, tool.flute_length_mm) == (1, 10.0, 30.0)
    assert [(p.number, p.axial_offset_mm, p.register_radius_mm) for p in tool.points] == [
        (1, 0.0, 0.0)
    ]


@pytest.mark.req("REQ-SHT-009")
def test_the_operations_header_values(ctx: Context) -> None:
    (op,) = _sheet(ctx).operations
    assert (op.name, op.strategy, op.tool_number) == ("PROFILE_1", "profile", 1)
    assert (op.point_number, op.axial_offset_mm, op.register_radius_mm) == (1, 0.0, 0.0)
    assert (op.spindle_rpm, op.tol_mm) == (8000.0, 0.01)
    assert op.feeds == (("plunge", 300.0), ("cut", 1200.0))
    assert (op.clearance_mm, op.retract_mm, op.lowest_mm) == (5.0, 3.0, -10.0)


@pytest.mark.req("REQ-SHT-010", "REQ-SHT-011")
def test_one_approach_point_off_the_minus_y_face(ctx: Context) -> None:
    (point,) = _sheet(ctx).operations[0].approach_points
    assert (point.x_mm, point.y_mm) == P
    assert (point.descents, point.rapid_to_mm, point.lowest_mm) == (3, 3.0, -10.0)
    assert point.feeds_mm_min == (300.0,)
    assert point.side is Side.MINUS_Y
    assert point.centre_distance_mm == pytest.approx(6.0, abs=1e-12)
    assert point.gap_mm == pytest.approx(1.0, abs=1e-12)


@pytest.mark.req("REQ-SHT-011")
def test_an_approach_point_above_the_stock_top_has_no_side(ctx: Context) -> None:
    low = StockBox((-5.0, -5.0, -30.0), (105.0, 65.0, -10.0))
    (point,) = _sheet(ctx, low).operations[0].approach_points
    expected = ApproachPoint(50.0, -11.0, 3, 3.0, -10.0, (300.0,), None, None, None)
    assert point == expected


@pytest.mark.req("REQ-SHT-012")
def test_reach_keep_clear_and_holding(ctx: Context) -> None:
    sheet = _sheet(ctx)
    expected = Box3((-10.0, -16.0, -10.0), (110.0, 70.0, 5.0))
    assert sheet.operations[0].reach == expected
    assert sheet.reach == expected
    assert sheet.keep_clear == Box3((-15.0, -21.0, -10.0), (115.0, 75.0, 5.0))
    assert sheet.holds_below_mm == -10.0


@pytest.mark.req("REQ-SHT-012")
def test_no_holding_sentence_where_the_reach_does_not_cover_the_stock(ctx: Context) -> None:
    wide = StockBox((-5.0, -5.0, -20.0), (110.5, 65.0, 0.0))
    sheet = _sheet(ctx, wide)
    assert sheet.holds_below_mm is None
    # The boundary: a stock face on the reach's face is covered.
    edge = StockBox((-10.0, -5.0, -20.0), (110.0, 65.0, 0.0))
    stock_sheet = make_setup_sheet(golden_job(stock=edge), record(ctx), part(ctx), FILES, ctx)
    assert stock_sheet.holds_below_mm == -10.0


@pytest.mark.req("REQ-SHT-013")
def test_the_rapid_floor_is_the_lowest_clearance_height(ctx: Context) -> None:
    assert _sheet(ctx).rapid_floor_mm == 5.0


@pytest.mark.req("REQ-SHT-014")
@pytest.mark.parametrize(
    ("bottom", "reached"),
    [(-20.0, False), (-10.0, True), (-9.0, True), (math.nextafter(-10.0, -math.inf), False)],
)
def test_the_stock_bottom_reached_at_or_below(ctx: Context, bottom: float, reached: bool) -> None:
    stock = StockBox((-5.0, -5.0, bottom), (105.0, 65.0, 0.0))
    assert _sheet(ctx, stock).reaches_stock_bottom is reached


@pytest.mark.req("REQ-SHT-015")
def test_one_witness_mark_on_three_passes(ctx: Context) -> None:
    (mark,) = _sheet(ctx).operations[0].witness_marks
    assert (mark.centre_x_mm, mark.centre_y_mm) == (50.0, -5.0)
    assert (mark.contact_x_mm, mark.contact_y_mm) == (50.0, 0.0)
    assert mark.passes == 3


@pytest.mark.req("REQ-SHT-016")
def test_the_operation_ends_over_p(ctx: Context) -> None:
    assert _sheet(ctx).operations[0].end_xy_mm == P


@pytest.mark.req("REQ-SHT-006", "REQ-SHT-019")
def test_values_are_unrounded_copies(ctx: Context) -> None:
    stock = replace(STOCK, min_mm=(-5.0004, -5.0, -20.0))
    assert _sheet(ctx, stock).stock.min_mm == (-5.0004, -5.0, -20.0)
