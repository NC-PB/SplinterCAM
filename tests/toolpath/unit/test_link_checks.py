# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the heights and the plan's checks, each refusal naming its requirement, pass and
row, in the fixed order (REQ-TP-001, 007 to 014; research 10, Method and test 1)."""

import math
from dataclasses import replace

import numpy as np
import pytest

from cl_strategies import H_C, H_R, HEADER, P
from cl_strategies import refusal as cl_refusal
from splintercam.cl import ClHeader, Role
from splintercam.foundation import Context
from splintercam.model import StockBox
from splintercam.toolpath import LevelPass, LinkPlan, link_heights, link_operation
from toolpath_plans import STOCK, TOOL, profile_plan, refusal, square_pass, square_plan

_EDGE = 2.0**-10  # a dyadic step: the distance test of REQ-TP-012 is exact on these coordinates
_T2 = replace(TOOL, number=2)  # the header calls T1


def _with_top(top: float) -> StockBox:
    return StockBox((-5.0, -5.0, top - 15.0), (105.0, 65.0, top))


def _shifted(level: LevelPass, index: tuple[int, int], value: float) -> LevelPass:
    rows = level.rows.copy()
    rows[index] = value
    return replace(level, rows=rows)


@pytest.mark.req("REQ-TP-001")
@pytest.mark.parametrize(("top", "clearance", "retract"), [(2.0, 7.0, 5.0), (0.0, 5.0, 3.0)])
def test_link_heights_from_the_stock_top(top: float, clearance: float, retract: float) -> None:
    # Research 10 test 2 (top 2 mm: 7 and 5) and top 0 (5 and 3).
    heights = link_heights(_with_top(top))
    assert (heights.clearance_mm, heights.retract_mm) == (clearance, retract)


@pytest.mark.req("REQ-TP-001")
@pytest.mark.parametrize("top", [1e16, math.inf, math.nan])
def test_a_stock_top_without_two_heights_is_refused(ctx: Context, top: float) -> None:
    # At 1e16 both sums round to 1e16 + 4: h_r is not below h_c. link_heights does not raise.
    link_heights(_with_top(top))
    with pytest.raises(ValueError, match=refusal("REQ-TP-001")):
        link_operation(HEADER, square_plan(), _with_top(top), ctx)


@pytest.mark.req("REQ-TP-007")
@pytest.mark.parametrize("field", ["clearance_height_mm", "retract_height_mm"])
@pytest.mark.parametrize("delta", [-0.001, 0.001])
def test_header_heights_off_h_c_or_h_r_are_refused(ctx: Context, field: str, delta: float) -> None:
    value = {"clearance_height_mm": H_C, "retract_height_mm": H_R}[field] + delta
    header = replace(HEADER, **{field: value})
    with pytest.raises(ValueError, match=refusal("REQ-TP-007")):
        link_operation(header, square_plan(), STOCK, ctx)


@pytest.mark.req("REQ-TP-007")
@pytest.mark.parametrize("field", ["clearance_height_mm", "retract_height_mm"])
@pytest.mark.parametrize("direction", [-math.inf, math.inf])
def test_header_heights_one_ulp_off_are_refused(ctx: Context, field: str, direction: float) -> None:
    # Bit for bit: no tolerance.
    base = {"clearance_height_mm": H_C, "retract_height_mm": H_R}[field]
    header = replace(HEADER, **{field: math.nextafter(base, direction)})
    with pytest.raises(ValueError, match=refusal("REQ-TP-007") + f" header {field[:-10]}"):
        link_operation(header, square_plan(), STOCK, ctx)


@pytest.mark.req("REQ-TP-008")
@pytest.mark.parametrize(
    ("plan", "text"),
    [
        (LinkPlan(P, TOOL, 0, ()), "no pass"),
        (LinkPlan((math.nan, -15.0), TOOL, 0, ()), "no pass"),
        (LinkPlan((math.nan, -15.0), TOOL, -1, (square_pass(-1.0),)), "approach point"),
        (LinkPlan((50.0, math.inf), TOOL, 0, (square_pass(-1.0),)), "approach point"),
        (LinkPlan(P, TOOL, -1, (square_pass(-1.0),)), "plunge feed class"),
        (LinkPlan(P, TOOL, 2**63, (square_pass(-1.0),)), "plunge feed class"),
        (LinkPlan(P, _T2, 0, (square_pass(-1.0),)), "tool number"),
        (LinkPlan(P, _T2, -1, (square_pass(-1.0),)), "plunge feed class"),
    ],
    ids=["no pass", "no pass before P", "P NaN before plunge", "P infinite",
         "plunge class negative", "plunge class beyond int64 (DEC-TP-005)",
         "tool number (AQ-020)", "plunge class before tool number"],
)  # fmt: skip
def test_a_broken_plan_field_is_refused(ctx: Context, plan: LinkPlan, text: str) -> None:
    with pytest.raises(ValueError, match=refusal("REQ-TP-008") + f" {text}"):
        link_operation(HEADER, plan, STOCK, ctx)


def _pass_with(column: str, value: object) -> LevelPass:
    return replace(square_pass(-1.0), **{column: value})


@pytest.mark.req("REQ-TP-009")
@pytest.mark.parametrize(
    ("broken", "column"),
    [
        (_pass_with("rows", square_pass(-1.0).rows.astype(np.float32)), "rows"),
        (_pass_with("rows", square_pass(-1.0).rows[:, :6].copy()), "rows"),
        (_pass_with("rows", square_pass(-1.0).rows.tolist()), "rows"),
        (_pass_with("rows", np.ma.masked_array(square_pass(-1.0).rows)), "rows"),
        (_pass_with("role", square_pass(-1.0).role[:3].copy()), "role"),
        (_pass_with("role", square_pass(-1.0).role.astype(np.int64)), "role"),
        (_pass_with("feed_class", square_pass(-1.0).feed_class.astype(np.int32)), "feed_class"),
        (_pass_with("feed_class", square_pass(-1.0).feed_class.reshape(4, 1)), "feed_class"),
        (_pass_with("role", np.array(Role.CUT, dtype=np.int8)), "role"),
    ],
    ids=["float32", "(m, 6)", "list", "masked", "role short", "role int64", "feed int32",
         "feed (m, 1)", "role 0-d"],
)  # fmt: skip
def test_a_broken_column_names_the_pass_and_column(
    ctx: Context, broken: LevelPass, column: str
) -> None:
    plan = LinkPlan(P, TOOL, 0, (square_pass(-2.0), broken))
    with pytest.raises(ValueError, match=refusal("REQ-TP-009", 1) + f" column {column} "):
        link_operation(HEADER, plan, STOCK, ctx)


@pytest.mark.req("REQ-TP-009")
def test_an_empty_pass_is_refused(ctx: Context) -> None:
    empty = LevelPass(
        -1.0, np.zeros((0, 7)), np.zeros(0, dtype=np.int8), np.zeros(0, dtype=np.int64)
    )
    with pytest.raises(ValueError, match=refusal("REQ-TP-009", 0) + " .*no row"):
        link_operation(HEADER, LinkPlan(P, TOOL, 0, (empty,)), STOCK, ctx)


@pytest.mark.req("REQ-TP-009")
@pytest.mark.parametrize("role", [Role.LINK, 7])
def test_a_row_role_other_than_approach_cut_retract_is_refused(ctx: Context, role: int) -> None:
    level = square_pass(-1.0)
    roles = level.role.copy()
    roles[2] = role
    plan = LinkPlan(P, TOOL, 0, (replace(level, role=roles),))
    with pytest.raises(ValueError, match=refusal("REQ-TP-009", 0, 2) + " .*role"):
        link_operation(HEADER, plan, STOCK, ctx)


@pytest.mark.req("REQ-TP-010")
@pytest.mark.parametrize("z", [H_R, 4.0, math.nan, -math.inf])
def test_a_level_not_below_h_r_is_refused(ctx: Context, z: float) -> None:
    with pytest.raises(ValueError, match=refusal("REQ-TP-010", 1)):
        link_operation(HEADER, square_plan(-1.0, z), STOCK, ctx)


@pytest.mark.req("REQ-TP-010")
def test_a_level_one_ulp_below_the_stock_bottom_is_refused(ctx: Context) -> None:
    # AQ-021 (a): below the stock bottom (-15) is the vice or the table.
    below = math.nextafter(STOCK.min_mm[2], -math.inf)
    with pytest.raises(ValueError, match=refusal("REQ-TP-010", 1) + " level .* stock bottom"):
        link_operation(HEADER, square_plan(-1.0, below), STOCK, ctx)


@pytest.mark.req("REQ-TP-010")
def test_a_level_at_the_stock_bottom_passes(ctx: Context) -> None:
    moves = link_operation(HEADER, square_plan(STOCK.min_mm[2]), STOCK, ctx).moves
    assert moves.end_mm[3, 2] == STOCK.min_mm[2]


@pytest.mark.req("REQ-TP-010")
def test_a_level_one_ulp_below_h_r_passes(ctx: Context) -> None:
    moves = link_operation(HEADER, square_plan(math.nextafter(H_R, -math.inf)), STOCK, ctx).moves
    assert moves.end_mm[3, 2] == math.nextafter(H_R, -math.inf)


@pytest.mark.req("REQ-TP-011")
@pytest.mark.parametrize(
    ("index", "row"),
    [((0, 0), 0), ((0, 1), 0), ((2, 0), 2), ((2, 1), 2), ((3, 2), 3), ((3, 3), 3)],
    ids=["first start x", "first start y", "chain x", "chain y", "last end x", "last end y"],
)
def test_a_pass_off_p_or_with_a_gap_by_one_ulp_is_refused(
    ctx: Context, index: tuple[int, int], row: int
) -> None:
    level = square_pass(-1.0)
    value = math.nextafter(float(level.rows[index]), math.inf)
    plan = LinkPlan(P, TOOL, 0, (square_pass(-2.0), _shifted(level, index, value)))
    with pytest.raises(ValueError, match=refusal("REQ-TP-011", 1, row)):
        link_operation(HEADER, plan, STOCK, ctx)


@pytest.mark.req("REQ-TP-011")
def test_the_first_break_in_a_pass_is_named_in_the_stated_order(ctx: Context) -> None:
    # Start off P and end off P: the start is checked first.
    level = square_pass(-1.0)
    broken = _shifted(_shifted(level, (3, 2), 51.0), (0, 0), 51.0)
    with pytest.raises(ValueError, match=refusal("REQ-TP-011", 0, 0)):
        link_operation(HEADER, LinkPlan(P, TOOL, 0, (broken,)), STOCK, ctx)


@pytest.mark.req("REQ-TP-011")
def test_a_profile_pass_ending_1e_9_from_p_is_refused(ctx: Context) -> None:
    # Example part: the last row ends 1e-9 mm from P.
    plan = profile_plan()
    last = plan.passes[0].rows.shape[0] - 1
    broken = _shifted(plan.passes[0], (last, 2), P[0] + 1e-9)
    with pytest.raises(ValueError, match=refusal("REQ-TP-011", 0, last)):
        link_operation(HEADER, replace(plan, passes=(broken, *plan.passes[1:])), STOCK, ctx)


def _at(point: tuple[float, float]) -> LinkPlan:
    return LinkPlan(point, TOOL, 0, (square_pass(-1.0, point),))


@pytest.mark.req("REQ-TP-012", "REQ-TP-014")
@pytest.mark.parametrize(
    "point",
    [(50.0, -10.0), (110.0, 30.0), (-8.0, -9.0), (50.0, 30.0), (50.0, -7.0)],
    ids=["R below a side", "R right of a side", "corner 3-4-5", "inside", "2 mm off a side"],
)
def test_a_descent_within_r_of_the_stock_box_is_refused(
    ctx: Context, point: tuple[float, float]
) -> None:
    with pytest.raises(ValueError, match=refusal("REQ-TP-012")):
        link_operation(HEADER, _at(point), STOCK, ctx)


@pytest.mark.req("REQ-TP-012", "REQ-TP-014")
@pytest.mark.parametrize(
    "point",
    [(50.0, -10.0 - _EDGE), (110.0 + _EDGE, 30.0), (-8.0, -9.0 - _EDGE), (-10.0 - _EDGE, 0.0)],
    ids=["below a side", "right of a side", "off a corner", "left of a side"],
)
def test_a_descent_just_beyond_r_of_the_stock_box_passes(
    ctx: Context, point: tuple[float, float]
) -> None:
    moves = link_operation(HEADER, _at(point), STOCK, ctx).moves
    assert tuple(moves.end_mm[1, :2]) == point


@pytest.mark.req("REQ-TP-012")
@pytest.mark.parametrize("corner", [0, 1])
@pytest.mark.parametrize("axis", [0, 1])
def test_a_stock_box_not_finite_in_xy_is_refused(ctx: Context, corner: int, axis: int) -> None:
    # DEC-TP-005: Python's max() would drop a NaN and let P in the stock's middle pass.
    ends = [list(STOCK.min_mm), list(STOCK.max_mm)]
    ends[corner][axis] = math.nan
    stock = StockBox((ends[0][0], ends[0][1], ends[0][2]), (ends[1][0], ends[1][1], ends[1][2]))
    with pytest.raises(ValueError, match=refusal("REQ-TP-012")):
        link_operation(HEADER, _at((50.0, 30.0)), stock, ctx)


@pytest.mark.req("REQ-TP-013")
def test_the_first_rule_broken_is_named_over_the_first_pass(ctx: Context) -> None:
    # Pass 0 breaks REQ-TP-011, pass 1 REQ-TP-009: rule by rule, so REQ-TP-009 and pass 1.
    first = _shifted(square_pass(-1.0), (0, 0), 50.5)
    second = replace(square_pass(-2.0), rows=square_pass(-2.0).rows.astype(np.float32))
    plan = LinkPlan(P, TOOL, 0, (first, second))
    with pytest.raises(ValueError, match=refusal("REQ-TP-009", 1)):
        link_operation(HEADER, plan, STOCK, ctx)


@pytest.mark.req("REQ-TP-013")
def test_the_first_pass_and_row_breaking_a_rule_are_named(ctx: Context) -> None:
    with pytest.raises(ValueError, match=refusal("REQ-TP-010", 0)):
        link_operation(HEADER, square_plan(H_R, H_R), STOCK, ctx)
    level = square_pass(-1.0)
    roles = level.role.copy()
    roles[1:] = Role.LINK
    plan = LinkPlan(P, TOOL, 0, (replace(level, role=roles),))
    with pytest.raises(ValueError, match=refusal("REQ-TP-009", 0, 1)):
        link_operation(HEADER, plan, STOCK, ctx)


def _float32(z: float) -> LevelPass:
    return replace(square_pass(z), rows=square_pass(z).rows.astype(np.float32))


@pytest.mark.req("REQ-TP-013")
@pytest.mark.parametrize(
    ("header", "stock", "plan", "requirement"),
    [
        (replace(HEADER, clearance_height_mm=0.0), _with_top(1e16), square_plan(), "REQ-TP-001"),
        (replace(HEADER, clearance_height_mm=0.0), STOCK, LinkPlan(P, TOOL, 0, ()), "REQ-TP-007"),
        (HEADER, STOCK, LinkPlan(P, TOOL, -1, (square_pass(H_R),)), "REQ-TP-008"),
        (HEADER, STOCK, LinkPlan((50.0, 30.0), TOOL, 0, (square_pass(H_R),)), "REQ-TP-010"),
        (HEADER, STOCK, LinkPlan((50.0, 30.0), TOOL, 0, (square_pass(-1.0),)), "REQ-TP-011"),
        (HEADER, STOCK, LinkPlan(P, TOOL, -1, (_float32(H_R),)), "REQ-TP-008"),
        (HEADER, STOCK, LinkPlan(P, TOOL, 0, (_float32(H_R),)), "REQ-TP-009"),
        (HEADER, STOCK, LinkPlan((50.0, 30.0), TOOL, 2, (square_pass(-1.0, (50.0, 30.0)),)),
         "REQ-TP-012"),
    ],
    ids=["001 before 007", "007 before 008", "008 before 010", "010 before 011 and 012",
         "011 before 012", "008 before 009", "009 before 010", "012 before make_operation"],
)  # fmt: skip
def test_the_rules_run_in_order(
    ctx: Context, header: ClHeader, stock: StockBox, plan: LinkPlan, requirement: str
) -> None:
    with pytest.raises(ValueError, match=refusal(requirement)):
        link_operation(header, plan, stock, ctx)


@pytest.mark.req("REQ-TP-002")
def test_cls_refusal_passes_through_at_the_stated_move_index(ctx: Context) -> None:
    # Pass 1, row 2 with feed class 7 (the header has two): move 2 + (4 + 3) + 2 + 2 = 13.
    level = square_pass(-2.0)
    feeds = level.feed_class.copy()
    feeds[2] = 7
    plan = LinkPlan(P, TOOL, 0, (square_pass(-1.0), replace(level, feed_class=feeds)))
    with pytest.raises(ValueError, match=cl_refusal("REQ-CL-009", 13)):
        link_operation(HEADER, plan, STOCK, ctx)


@pytest.mark.req("REQ-TP-005", "REQ-TP-008")
def test_the_plunge_class_beyond_the_header_is_cls_to_refuse(ctx: Context) -> None:
    # REQ-TP-008 checks only the lower bound; the descent of pass 0 is move 3.
    plan = LinkPlan(P, TOOL, 2, (square_pass(-1.0),))
    with pytest.raises(ValueError, match=cl_refusal("REQ-CL-009", 3)):
        link_operation(HEADER, plan, STOCK, ctx)
