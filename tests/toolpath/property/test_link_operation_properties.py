# SPDX-License-Identifier: Apache-2.0
"""Property tests: random valid plans give REQ-TP-002's pattern, which `make_operation` accepts,
with research 10 test 1's invariants; one field broken at a time raises naming its requirement
(REQ-TP-002 to 006, 009 to 012)."""

import math
from dataclasses import replace

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from splintercam.cl import NO_FEED_CLASS, ClMoves, MoveKind, Role
from splintercam.foundation import Context
from splintercam.model import StockBox
from splintercam.toolpath import LevelPass, LinkHeights, LinkPlan, link_heights, link_operation
from toolpath_plans import header_for, plans, refusal

# The ctx fixture is a frozen value, the same for every example.
_SETTINGS = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])


def _check_pass(
    moves: ClMoves, first: int, plan: LinkPlan, level: LevelPass, heights: LinkHeights
) -> None:
    px, py = plan.approach_xy_mm
    m = level.rows.shape[0]
    assert moves.kind[first] == MoveKind.RAPID
    assert tuple(moves.end_mm[first]) == (px, py, heights.retract_mm)
    assert moves.link_height_mm[first] == heights.retract_mm
    assert (moves.kind[first + 1], moves.role[first + 1]) == (MoveKind.LINE, Role.APPROACH)
    assert moves.feed_class[first + 1] == plan.plunge_feed_class
    assert tuple(moves.end_mm[first + 1]) == (px, py, level.z_mm)
    cut = slice(first + 2, first + 2 + m)
    arc = level.rows[:, 6] != 0.0
    np.testing.assert_array_equal(moves.end_mm[cut, :2], level.rows[:, 2:4])
    assert (moves.end_mm[cut, 2] == level.z_mm).all()
    np.testing.assert_array_equal(moves.kind[cut], np.where(arc, MoveKind.ARC, MoveKind.LINE))
    np.testing.assert_array_equal(moves.centre_mm[cut][arc], level.rows[arc, 4:6])
    np.testing.assert_array_equal(moves.sweep_rad[cut], np.where(arc, level.rows[:, 6], 0.0))
    np.testing.assert_array_equal(moves.role[cut], level.role)
    np.testing.assert_array_equal(moves.feed_class[cut], level.feed_class)
    assert moves.kind[first + 2 + m] == MoveKind.RAPID
    assert tuple(moves.end_mm[first + 2 + m]) == (px, py, heights.clearance_mm)
    assert moves.link_height_mm[first + 2 + m] == heights.clearance_mm


@pytest.mark.req("REQ-TP-002", "REQ-TP-003", "REQ-TP-004", "REQ-TP-005", "REQ-TP-006")
@_SETTINGS
@given(plans())
def test_valid_plans_give_the_pattern(ctx: Context, drawn: tuple[LinkPlan, StockBox]) -> None:
    plan, stock = drawn
    heights = link_heights(stock)
    moves = link_operation(header_for(stock), plan, stock, ctx).moves
    sizes = [level.rows.shape[0] for level in plan.passes]
    assert moves.kind.shape[0] == 2 + sum(m + 3 for m in sizes)
    assert moves.end_mm[0, 2] == heights.clearance_mm
    assert np.isnan(moves.end_mm[0, :2]).all()
    assert tuple(moves.end_mm[1]) == (*plan.approach_xy_mm, heights.clearance_mm)
    first = 2
    for level, m in zip(plan.passes, sizes, strict=True):
        _check_pass(moves, first, plan, level, heights)
        first += m + 3


@pytest.mark.req("REQ-TP-004", "REQ-TP-012")
@_SETTINGS
@given(plans())
def test_research_10_test_1s_invariants(ctx: Context, drawn: tuple[LinkPlan, StockBox]) -> None:
    plan, stock = drawn
    heights = link_heights(stock)
    moves = link_operation(header_for(stock), plan, stock, ctx).moves
    rapid = moves.kind == MoveKind.RAPID
    start = np.vstack((np.full((1, 3), np.nan), moves.end_mm[:-1]))
    in_plane = (start[:, 0] != moves.end_mm[:, 0]) | (start[:, 1] != moves.end_mm[:, 1])
    # No RAPID in the plane below h_c; every rapid at its link height, LINK, without a feed class.
    assert (moves.end_mm[rapid & in_plane, 2] == heights.clearance_mm).all()
    assert (moves.link_height_mm[rapid & in_plane] == heights.clearance_mm).all()
    np.testing.assert_array_equal(moves.end_mm[rapid, 2], moves.link_height_mm[rapid])
    assert (moves.role[rapid] == Role.LINK).all()
    assert (moves.feed_class[rapid] == NO_FEED_CLASS).all()
    # Every move between the passes is along Z at P (Peter's answer to plan 0007, question 4).
    links = np.flatnonzero(rapid)[1:]
    np.testing.assert_array_equal(
        moves.end_mm[links, :2], np.array([plan.approach_xy_mm] * len(links))
    )
    assert (moves.end_mm[rapid, 2] >= heights.retract_mm).all()


_BREAKS = ("level", "start", "role", "dtype", "approach")


def _broken(plan: LinkPlan, stock: StockBox, how: str, index: int) -> tuple[LinkPlan, str]:
    level = plan.passes[index]
    if how == "approach":  # P in the middle of the stock box
        centre = (50.0, 30.0)
        moved = tuple(
            replace(p, rows=_moved(p.rows, plan.approach_xy_mm, centre)) for p in plan.passes
        )
        return replace(plan, approach_xy_mm=centre, passes=moved), "REQ-TP-012"
    if how == "level":
        changed = replace(level, z_mm=stock.top_mm + 3.0)
        requirement = "REQ-TP-010"
    elif how == "start":
        rows = level.rows.copy()
        rows[0, 0] = math.nextafter(float(rows[0, 0]), math.inf)
        changed, requirement = replace(level, rows=rows), "REQ-TP-011"
    elif how == "role":
        roles = level.role.copy()
        roles[-1] = Role.LINK
        changed, requirement = replace(level, role=roles), "REQ-TP-009"
    else:
        changed, requirement = replace(level, rows=level.rows.astype(np.float32)), "REQ-TP-009"
    passes = (*plan.passes[:index], changed, *plan.passes[index + 1 :])
    return replace(plan, passes=passes), requirement


def _moved(
    rows: NDArray[np.float64], old: tuple[float, float], new: tuple[float, float]
) -> NDArray[np.float64]:
    # The pass's first start and last end moved from the old P to the new one.
    moved = rows.copy()
    moved[0, :2] = new
    moved[-1, 2:4] = new
    assert tuple(rows[0, :2]) == old
    return moved


@pytest.mark.req("REQ-TP-009", "REQ-TP-010", "REQ-TP-011", "REQ-TP-012", "REQ-TP-013")
@_SETTINGS
@given(plans(), st.sampled_from(_BREAKS), st.data())
def test_one_field_broken_names_its_requirement_and_pass(
    ctx: Context, drawn: tuple[LinkPlan, StockBox], how: str, data: st.DataObject
) -> None:
    plan, stock = drawn
    index = data.draw(st.integers(0, len(plan.passes) - 1))
    broken, requirement = _broken(plan, stock, how, index)
    where = None if requirement == "REQ-TP-012" else index
    with pytest.raises(ValueError, match=refusal(requirement, where)):
        link_operation(header_for(stock), broken, stock, ctx)
