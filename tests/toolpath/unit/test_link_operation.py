# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the links of one operation: the order of the moves, their kinds, roles, ends and
link heights, and a pass's rows as LINE and ARC moves (REQ-TP-002 to 006; research 10, Method)."""

import math
from dataclasses import fields

import numpy as np
import pytest

from cl_strategies import CUT, H_C, H_R, HEADER, PASSES, PLUNGE, P, columns, profile_moves
from splintercam.cl import NO_FEED_CLASS, ClMoves, MoveKind, Role
from splintercam.foundation import Context
from splintercam.toolpath import LinkPlan, link_operation
from toolpath_plans import STOCK, TOOL, arc_row, level, line_row, profile_plan

_M = 11  # rows per pass in research 22 test 1's plan


def _moves(plan: LinkPlan, ctx: Context) -> ClMoves:
    return link_operation(HEADER, plan, STOCK, ctx).moves


@pytest.mark.req("REQ-TP-002", "REQ-TP-004", "REQ-TP-006")
def test_research_22_test_1_gives_cls_profile_record(ctx: Context) -> None:
    # The same 44 moves as cl's hand-written record of research 22 test 1, column by column.
    moves = _moves(profile_plan(), ctx)
    expected = columns(profile_moves())
    assert moves.kind.shape[0] == 2 + 3 * (_M + 3)
    for field in fields(ClMoves):
        np.testing.assert_array_equal(getattr(moves, field.name), getattr(expected, field.name))


@pytest.mark.req("REQ-TP-002")
def test_research_22_test_1s_kinds_roles_and_ends(ctx: Context) -> None:
    moves = _moves(profile_plan(), ctx)
    for i, z in enumerate(PASSES):
        first = 2 + i * (_M + 3)
        last = first + _M + 2
        assert moves.kind[first] == MoveKind.RAPID
        assert moves.kind[first + 1] == MoveKind.LINE
        assert moves.role[first + 1] == Role.APPROACH
        assert tuple(moves.end_mm[first]) == (*P, H_R)
        assert tuple(moves.end_mm[first + 1]) == (*P, z)
        assert (moves.end_mm[first + 2 : last, 2] == z).all()
        assert moves.kind[last] == MoveKind.RAPID
        assert tuple(moves.end_mm[last]) == (*P, H_C)


@pytest.mark.req("REQ-TP-003")
def test_the_first_move_is_along_z_and_the_second_in_the_plane_at_h_c(ctx: Context) -> None:
    moves = _moves(profile_plan(), ctx)
    assert moves.kind[0] == MoveKind.RAPID
    assert math.isnan(moves.end_mm[0, 0])
    assert math.isnan(moves.end_mm[0, 1])
    assert moves.end_mm[0, 2] == H_C
    assert moves.kind[1] == MoveKind.RAPID
    assert tuple(moves.end_mm[1]) == (*P, H_C)


@pytest.mark.req("REQ-TP-004")
def test_rapids_carry_h_c_but_the_descent_to_h_r(ctx: Context) -> None:
    moves = _moves(profile_plan(), ctx)
    rapid = moves.kind == MoveKind.RAPID
    descents = [2 + i * (_M + 3) for i in range(3)]
    expected = np.full(rapid.sum(), H_C)
    expected[[2 + 2 * i for i in range(3)]] = H_R  # the rapids: 0, 1, then per pass down and up
    np.testing.assert_array_equal(moves.link_height_mm[rapid], expected)
    np.testing.assert_array_equal(moves.link_height_mm[descents], H_R)
    assert (moves.role[rapid] == Role.LINK).all()
    assert (moves.feed_class[rapid] == NO_FEED_CLASS).all()
    assert np.isnan(moves.link_height_mm[~rapid]).all()


@pytest.mark.req("REQ-TP-005")
def test_each_descent_is_a_line_at_the_plunge_feed_class(ctx: Context) -> None:
    moves = _moves(profile_plan(plunge=CUT), ctx)
    for i, z in enumerate(PASSES):
        descent = 3 + i * (_M + 3)
        assert moves.kind[descent] == MoveKind.LINE
        assert moves.role[descent] == Role.APPROACH
        assert moves.feed_class[descent] == CUT
        assert tuple(moves.end_mm[descent]) == (*P, z)


@pytest.mark.req("REQ-TP-006")
def test_a_line_and_a_cw_arc_become_line_and_arc_moves(ctx: Context) -> None:
    # P (50, -15) to (40, -15), then a CW half circle about (45, -15) back to P; z = -2.
    rows = [line_row(P, (40.0, -15.0)), arc_row((40.0, -15.0), P, (45.0, -15.0), -math.pi)]
    plan = LinkPlan(P, TOOL, PLUNGE, (level(-2.0, rows, [Role.CUT, Role.RETRACT], [CUT, PLUNGE]),))
    moves = _moves(plan, ctx)
    assert list(moves.kind[4:6]) == [MoveKind.LINE, MoveKind.ARC]
    assert list(moves.role[4:6]) == [Role.CUT, Role.RETRACT]
    assert list(moves.feed_class[4:6]) == [CUT, PLUNGE]
    assert tuple(moves.end_mm[4]) == (40.0, -15.0, -2.0)
    assert tuple(moves.end_mm[5]) == (*P, -2.0)
    assert tuple(moves.centre_mm[5]) == (45.0, -15.0)
    assert moves.sweep_rad[5] == -math.pi
    assert np.isnan(moves.centre_mm[4]).all()
    assert np.isnan(moves.link_height_mm[4:6]).all()


@pytest.mark.req("REQ-TP-006")
def test_a_line_row_gets_the_fill_values_whatever_it_holds(ctx: Context) -> None:
    rows = [(*P, 40.0, -15.0, 0.0, 0.0, -0.0), (40.0, -15.0, *P, 0.0, 0.0, 0.0)]
    plan = LinkPlan(P, TOOL, PLUNGE, (level(-2.0, rows, [Role.CUT] * 2, [CUT] * 2),))
    moves = _moves(plan, ctx)
    assert list(moves.kind[4:6]) == [MoveKind.LINE, MoveKind.LINE]
    assert np.isnan(moves.centre_mm[4:6]).all()
    assert not np.signbit(moves.sweep_rad[4:6]).any()
    assert (moves.sweep_rad[4:6] == 0.0).all()


@pytest.mark.req("REQ-TP-006")
def test_a_whole_number_level_gives_float_columns(ctx: Context) -> None:
    # cnc review: an int z_mm must not make the end or link-height column an integer one.
    rows = [line_row(P, (40.0, -15.0)), line_row((40.0, -15.0), P)]
    plan = LinkPlan(P, TOOL, PLUNGE, (level(-2, rows, [Role.CUT] * 2, [CUT] * 2),))
    moves = _moves(plan, ctx)
    assert tuple(moves.end_mm[4]) == (40.0, -15.0, -2.0)
    assert np.isnan(moves.link_height_mm[4:6]).all()


@pytest.mark.req("REQ-TP-002", "REQ-TP-006")
def test_the_record_is_read_only_and_leaves_the_plan_alone(ctx: Context) -> None:
    plan = profile_plan()
    before = plan.passes[0].rows.copy()
    moves = _moves(plan, ctx)
    assert not moves.end_mm.flags.writeable
    np.testing.assert_array_equal(plan.passes[0].rows, before)
