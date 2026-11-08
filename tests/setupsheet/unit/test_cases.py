# SPDX-License-Identifier: Apache-2.0
"""The SPEC's other example parts and edge cases (src/splintercam/setupsheet/SPEC.md, Example
parts; REQ-SHT-008 to 016, 019)."""

import math
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import numpy as np
import pytest

from cl_strategies import CUT, H_R, NAN, PLUNGE, Move, arc, line, rapid
from setupsheet_cases import (
    FILES,
    HEADER,
    NAME,
    STOCK,
    TOOL,
    golden_job,
    job_operation,
    part,
    profile_moves,
    record,
)
from splintercam.cl import Role
from splintercam.foundation import Context
from splintercam.model import FlatEndMill, MeasurementPoint, StockBox
from splintercam.setupsheet import Box3, SheetPoint, Side, make_setup_sheet

_SRC = Path(__file__).parents[3] / "src" / "splintercam" / "setupsheet"


@pytest.mark.req("REQ-SHT-010", "REQ-SHT-015")
def test_p_equal_to_s_has_no_witness_mark(ctx: Context) -> None:
    data = record(ctx, ((HEADER, profile_moves((50.0, -5.0))),))
    low = StockBox((0.0, 0.0, -30.0), (100.0, 60.0, -11.0))  # P = S is beside this stock
    sheet = make_setup_sheet(golden_job(stock=low), data, part(ctx), FILES, ctx)
    op = sheet.operations[0]
    assert op.witness_marks == ()
    assert [(p.x_mm, p.y_mm, p.descents) for p in op.approach_points] == [(50.0, -5.0, 3)]


@pytest.mark.req("REQ-SHT-010", "REQ-SHT-012", "REQ-SHT-016")
def test_an_operation_of_one_rapid(ctx: Context) -> None:
    data = record(ctx, ((HEADER, [rapid(NAN, NAN, 5.0, 5.0)]),))
    sheet = make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx)
    op = sheet.operations[0]
    assert (op.approach_points, op.witness_marks, op.reach, op.end_xy_mm) == ((), (), None, None)
    assert op.lowest_mm == 5.0
    assert (sheet.reach, sheet.keep_clear, sheet.holds_below_mm) == (None, None, None)
    assert not sheet.reaches_stock_bottom


def _tool_with_points() -> FlatEndMill:
    points = (*TOOL.points, MeasurementPoint(2, 3.0, 0.0), MeasurementPoint(3, 2.0, 4.0))
    return replace(TOOL, points=points)


@pytest.mark.req("REQ-SHT-008")
def test_an_unused_point_is_not_listed(ctx: Context) -> None:
    job = golden_job(tools=(_tool_with_points(),))
    sheet = make_setup_sheet(job, record(ctx), part(ctx), FILES, ctx)
    assert sheet.tools[0].points == (SheetPoint(1, 0.0, 0.0),)


@pytest.mark.req("REQ-SHT-008", "REQ-SHT-009")
def test_used_points_are_listed_ascending_and_named_per_operation(ctx: Context) -> None:
    job = golden_job((job_operation("A", point=3), job_operation("B", point=2)),
                     tools=(_tool_with_points(),))  # fmt: skip
    headers = (replace(HEADER, name="A", point_number=3, axial_offset_mm=2.0),
               replace(HEADER, name="B", point_number=2, axial_offset_mm=3.0))  # fmt: skip
    data = record(ctx, [(h, profile_moves()) for h in headers])
    sheet = make_setup_sheet(job, data, part(ctx), FILES, ctx)
    assert sheet.tools[0].points == (SheetPoint(2, 3.0, 0.0), SheetPoint(3, 2.0, 4.0))
    named = [(o.point_number, o.axial_offset_mm, o.register_radius_mm) for o in sheet.operations]
    assert named == [(3, 2.0, 4.0), (2, 3.0, 0.0)]


def _second_operation() -> list[Move]:
    """T2 D 6 at h_c 8: down at (120, 30), a cut to X 108 and back, up to h_c."""
    return [rapid(NAN, NAN, 8.0, 8.0), rapid(120.0, 30.0, 8.0, 8.0),
            rapid(120.0, 30.0, H_R, H_R), line(120.0, 30.0, -2.0, Role.APPROACH, PLUNGE),
            line(108.0, 30.0, -2.0), line(120.0, 30.0, -2.0, Role.RETRACT, CUT),
            rapid(120.0, 30.0, 8.0, 8.0)]  # fmt: skip


@pytest.mark.req("REQ-SHT-008", "REQ-SHT-011", "REQ-SHT-012", "REQ-SHT-013")
def test_two_operations_with_two_tools(ctx: Context) -> None:
    job = golden_job((job_operation("A"), job_operation("B", tool=2)),
                     tools=(FlatEndMill(2, 6.0, 20.0), TOOL))  # fmt: skip
    second = replace(HEADER, name="B", tool_number=2, clearance_height_mm=8.0)
    data = record(ctx, ((replace(HEADER, name="A"), profile_moves()),
                        (second, _second_operation())))  # fmt: skip
    sheet = make_setup_sheet(job, data, part(ctx), FILES, ctx)
    assert [t.number for t in sheet.tools] == [1, 2]
    assert sheet.operations[1].reach == Box3((105.0, 27.0, -2.0), (123.0, 33.0, 8.0))
    assert sheet.reach == Box3((-10.0, -16.0, -10.0), (123.0, 70.0, 8.0))
    assert sheet.keep_clear == Box3((-15.0, -21.0, -10.0), (128.0, 75.0, 8.0))
    assert sheet.rapid_floor_mm == 5.0
    assert sheet.holds_below_mm == -10.0  # the union covers the stock box in XY
    (point,) = sheet.operations[1].approach_points
    assert (point.side, point.centre_distance_mm, point.gap_mm) == (Side.PLUS_X, 15.0, 12.0)


@pytest.mark.req("REQ-SHT-011")
@pytest.mark.parametrize("y", [-10.0, -9.5, 0.0])
def test_an_approach_within_r_of_the_stock_box_is_refused(ctx: Context, y: float) -> None:
    data = record(ctx, ((HEADER, profile_moves((50.0, y))),))
    with pytest.raises(ValueError, match=rf"^setup sheet: operation '{NAME}': REQ-SHT-011: "
                                         rf"approach point X 50.0 Y {y}"):  # fmt: skip
        make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx)


@pytest.mark.req("REQ-SHT-011")
def test_just_beyond_r_passes_and_a_point_above_the_stock_is_not_refused(ctx: Context) -> None:
    beyond = record(ctx, ((HEADER, profile_moves((50.0, -10.0 - 2.0**-10))),))
    (point,) = (
        make_setup_sheet(golden_job(), beyond, part(ctx), FILES, ctx).operations[0].approach_points
    )
    assert point.gap_mm == pytest.approx(2.0**-10, abs=1e-12)
    inside = record(ctx, ((HEADER, profile_moves((50.0, -9.0))),))
    low = replace(STOCK, max_mm=(105.0, 65.0, -10.0))  # the lowest end -10 is not below the top
    sheet = make_setup_sheet(golden_job(stock=low), inside, part(ctx), FILES, ctx)
    assert sheet.operations[0].approach_points[0].side is None


@pytest.mark.req("REQ-SHT-011")
def test_a_point_off_a_corner(ctx: Context) -> None:
    data = record(ctx, ((HEADER, profile_moves((-9.0, -9.0))),))
    (point,) = (
        make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx).operations[0].approach_points
    )
    assert point.side is Side.CORNER
    assert point.centre_distance_mm == pytest.approx(math.sqrt(32.0), abs=1e-12)
    assert point.gap_mm == pytest.approx(math.sqrt(32.0) - 5.0, abs=1e-12)


@pytest.mark.req("REQ-SHT-010")
def test_minus_zero_is_the_same_xy_and_feeds_are_in_order_of_first_use(ctx: Context) -> None:
    moves = profile_moves(per_pass=((0.0, -11.0), (-0.0, -11.0), (0.0, -11.0)),
                          plunge_feeds=(PLUNGE, CUT, PLUNGE))  # fmt: skip
    data = record(ctx, ((HEADER, moves),))
    (point,) = (
        make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx).operations[0].approach_points
    )
    assert point.descents == 3
    assert math.copysign(1.0, point.x_mm) == 1.0  # the first value met
    assert point.feeds_mm_min == (300.0, 1200.0)


@pytest.mark.req("REQ-SHT-010", "REQ-SHT-015")
def test_points_and_marks_in_order_of_first_occurrence(ctx: Context) -> None:
    ps = ((50.0, -11.0), (40.0, -11.0), (50.0, -11.0))
    data = record(ctx, ((HEADER, profile_moves(per_pass=ps)),))
    op = make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx).operations[0]
    assert [(p.x_mm, p.descents) for p in op.approach_points] == [(50.0, 2), (40.0, 1)]
    # DEC-SHT-012: the oblique approach from (40, -11) stops at S too, so the tool touches the
    # wall Y 0 at the same point as the square one: one mark on all three passes.
    marks = [(m.contact_x_mm, m.contact_y_mm, m.passes) for m in op.witness_marks]
    assert marks == [(50.0, 0.0, 3)]


@pytest.mark.req("REQ-SHT-015")
def test_an_approach_along_the_wall_leaves_no_mark(ctx: Context) -> None:
    # P on the line of the first cut's wall, approached along it: no contact across the wall.
    data = record(ctx, ((HEADER, profile_moves((60.0, -5.0))),))
    low = StockBox((0.0, 0.0, -30.0), (100.0, 60.0, -11.0))
    sheet = make_setup_sheet(golden_job(stock=low), data, part(ctx), FILES, ctx)
    assert sheet.operations[0].witness_marks == ()


@pytest.mark.req("REQ-SHT-012", "REQ-SHT-015")
def test_a_mark_on_an_arc_lies_along_its_radius(ctx: Context) -> None:
    # From X 20 to S (10, 0), then a full circle CW about the origin: the boss of radius 5 is
    # touched at (5, 0), toward the centre, the side the approach moves to.
    moves = [rapid(NAN, NAN, 5.0, 5.0), rapid(20.0, 0.0, 5.0, 5.0), rapid(20.0, 0.0, H_R, H_R),
             line(20.0, 0.0, -1.0, Role.APPROACH, PLUNGE), line(10.0, 0.0, -1.0, Role.APPROACH),
             arc((10.0, 0.0, -1.0), (0.0, 0.0), -math.tau), rapid(10.0, 0.0, 5.0, 5.0)]  # fmt: skip
    low = StockBox((-5.0, -5.0, -30.0), (5.0, 5.0, -11.0))
    data = record(ctx, ((HEADER, moves),))
    op = make_setup_sheet(golden_job(stock=low), data, part(ctx), FILES, ctx).operations[0]
    (mark,) = op.witness_marks
    contact = (mark.centre_x_mm, mark.centre_y_mm, mark.contact_x_mm, mark.contact_y_mm)
    assert contact == (10.0, 0.0, 5.0, 0.0)
    # REQ-SHT-012: the circle bulges past its ends; the reach holds its extremes, grown by 5.
    assert op.reach == Box3((-15.0, -15.0, -1.0), (25.0, 15.0, 5.0))


@pytest.mark.req("REQ-SHT-011")
def test_the_corner_boundary_at_r_is_refused(ctx: Context) -> None:
    # dx 3, dy 4 off the corner (-5, -5): exactly R = 5, touching counts (REQ-TP-012).
    data = record(ctx, ((HEADER, profile_moves((-8.0, -9.0))),))
    with pytest.raises(ValueError, match=r"REQ-SHT-011: approach point X -8.0 Y -9.0"):
        make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx)


def _with_upward_moves(p: tuple[float, float]) -> list[Move]:
    """The golden record with, after each pass's S -> P, a feed retract along Z at P to Z -1 and
    a RAPID up to h_r: both end below h_c at P and go up."""
    moves: list[Move] = []
    for move in profile_moves(p):
        moves.append(move)
        if move.role is Role.RETRACT:
            moves += [line(*p, -1.0, Role.RETRACT, CUT), rapid(*p, H_R, H_R)]
    return moves


@pytest.mark.req("REQ-SHT-010")
def test_moves_going_up_are_no_descents_and_no_plunge_feeds(ctx: Context) -> None:
    data = record(ctx, ((HEADER, _with_upward_moves((50.0, -11.0))),))
    (point,) = (
        make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx).operations[0].approach_points
    )
    assert (point.descents, point.rapid_to_mm, point.lowest_mm) == (3, 3.0, -10.0)
    assert point.feeds_mm_min == (300.0,)


@pytest.mark.req("REQ-SHT-010")
def test_a_rapid_descent_with_a_ramp_has_no_plunge_feed(ctx: Context) -> None:
    # Down at P to h_r, then a ramp (not along Z alone) to S at Z -1: P's lowest end is h_r.
    moves = [rapid(NAN, NAN, 5.0, 5.0), rapid(50.0, -11.0, 5.0, 5.0),
             rapid(50.0, -11.0, H_R, H_R), line(50.0, -5.0, -1.0, Role.APPROACH, PLUNGE),
             line(5.0, -5.0, -1.0), line(5.0, -5.0, -3.0), rapid(5.0, -5.0, 5.0, 5.0)]  # fmt: skip
    data = record(ctx, ((HEADER, moves),))
    op = make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx).operations[0]
    # (5, -5) has a LINE along Z alone but no RAPID descent: no approach point.
    assert [(p.x_mm, p.y_mm, p.descents, p.lowest_mm) for p in op.approach_points] == [
        (50.0, -11.0, 1, 3.0)
    ]
    assert op.approach_points[0].feeds_mm_min == ()
    assert op.approach_points[0].side is None


@pytest.mark.req("REQ-SHT-019")
def test_inputs_unchanged_values_frozen_and_repeatable(ctx: Context) -> None:
    job, data, contour = golden_job(), record(ctx), part(ctx)
    ends = [np.array(op.moves.end_mm, copy=True) for op in data.operations]
    first = make_setup_sheet(job, data, contour, FILES, ctx)
    assert first == make_setup_sheet(job, data, contour, FILES, ctx)
    assert job == golden_job()
    for held, before in zip(data.operations, ends, strict=True):
        np.testing.assert_array_equal(held.moves.end_mm, before)
    with pytest.raises(FrozenInstanceError):
        first.work_offset = 2  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(FrozenInstanceError):
        first.operations[0].approach_points[0].x_mm = 0.0  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.req("REQ-SHT-019")
def test_no_clock_locale_or_environment_is_read() -> None:
    banned = ("import time", "import os", "import locale", "import datetime", "import random",
              "from time", "from os", "from locale", "from datetime", "from random")  # fmt: skip
    for source in sorted(_SRC.glob("*.py")):
        text = source.read_text(encoding="utf-8")
        assert not [b for b in banned if b in text], source.name
