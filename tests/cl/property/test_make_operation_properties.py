# SPDX-License-Identifier: Apache-2.0
"""Property tests: generated valid operations pass, read-only and unchanged; each one broken in
one value raises naming its requirement and move (REQ-CL-007, 011, 012, 016, 019, 020)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cl_strategies import H_C, HEADER, Move, changed, columns, operations
from splintercam.cl import ClMoves, MoveKind, make_operation
from splintercam.foundation import Context

# The ctx fixture is a frozen value, the same for every example.
_SETTINGS = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
_COLUMNS = ("kind", "role", "end_mm", "centre_mm", "sweep_rad", "feed_class", "link_height_mm")


def _refusal(moves: ClMoves, ctx: Context) -> str:
    try:
        make_operation(HEADER, moves, ctx)
    except ValueError as error:
        return str(error)
    raise AssertionError("not refused")


@pytest.mark.req("REQ-CL-016", "REQ-CL-019")
@_SETTINGS
@given(operations())
def test_valid_operations_pass_unchanged_and_read_only(ctx: Context, moves: list[Move]) -> None:
    """Implements: REQ-CL-016 (random consistent arcs pass), REQ-CL-019."""
    produced = columns(moves)
    held = make_operation(HEADER, produced, ctx).moves
    for name in _COLUMNS:
        np.testing.assert_array_equal(getattr(held, name), getattr(produced, name))
        assert not getattr(held, name).flags.writeable
        assert getattr(held, name) is not getattr(produced, name)


@pytest.mark.req("REQ-CL-007", "REQ-CL-020")
@_SETTINGS
@given(operations(), st.data())
def test_a_value_that_is_not_finite_names_its_move(
    ctx: Context, moves: list[Move], data: st.DataObject
) -> None:
    """Implements: REQ-CL-007, REQ-CL-020 (one value broken at a time)."""
    move = data.draw(st.integers(1, len(moves) - 1))
    axis = data.draw(st.integers(0, 2))
    value = data.draw(st.sampled_from((math.nan, math.inf, -math.inf)))
    message = _refusal(changed(columns(moves), "end_mm", (move, axis), value), ctx)
    assert message.startswith(f"operation 'Profile_1': REQ-CL-007: move {move}:")


@pytest.mark.req("REQ-CL-011", "REQ-CL-020")
@_SETTINGS
@given(operations(), st.data())
def test_a_rapid_ending_below_its_link_height_names_its_move(
    ctx: Context, moves: list[Move], data: st.DataObject
) -> None:
    """Implements: REQ-CL-011, REQ-CL-020."""
    rapids = [i for i, m in enumerate(moves) if m.kind == MoveKind.RAPID]
    move = data.draw(st.sampled_from(rapids))
    raised = math.nextafter(moves[move].end[2], math.inf)
    message = _refusal(changed(columns(moves), "link_height_mm", move, raised), ctx)
    assert message.startswith(f"operation 'Profile_1': REQ-CL-011: move {move}:")


@pytest.mark.req("REQ-CL-012", "REQ-CL-020")
@_SETTINGS
@given(operations(), st.data())
def test_a_last_rapid_below_the_clearance_height_is_named(
    ctx: Context, moves: list[Move], data: st.DataObject
) -> None:
    """Implements: REQ-CL-012, REQ-CL-020: the last rapid lowered, with its link height."""
    last = len(moves) - 1
    lower = data.draw(st.floats(-1.0, H_C, exclude_max=True))
    lowered = changed(columns(moves), "end_mm", (last, 2), lower)
    message = _refusal(changed(lowered, "link_height_mm", last, lower), ctx)
    assert message.startswith(f"operation 'Profile_1': REQ-CL-012: move {last}:")


@pytest.mark.req("REQ-CL-016", "REQ-CL-020")
@_SETTINGS
@given(operations(), st.data())
def test_an_arc_given_a_longer_sweep_names_its_move(
    ctx: Context, moves: list[Move], data: st.DataObject
) -> None:
    """Implements: REQ-CL-016, REQ-CL-020: the sweep lengthened by 3 eps_len / r, so the end lies
    3 eps_len along the circle from where the sweep reaches; no other move changes."""
    arcs = [i for i, m in enumerate(moves) if m.kind == MoveKind.ARC]
    if not arcs:
        return
    move = data.draw(st.sampled_from(arcs))
    centre, start = moves[move].centre, moves[move - 1].end
    radius = math.sqrt((start[0] - centre[0]) ** 2 + (start[1] - centre[1]) ** 2)
    sweep = moves[move].sweep
    longer = sweep + math.copysign(3 * ctx.tolerances.length_eps_mm / radius, sweep)
    message = _refusal(changed(columns(moves), "sweep_rad", move, longer), ctx)
    assert message.startswith(f"operation 'Profile_1': REQ-CL-016: move {move}:")
