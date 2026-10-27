# SPDX-License-Identifier: Apache-2.0
"""Property tests: generated valid operations pass, read-only and unchanged; each one broken in
one value raises naming its requirement and move (REQ-CL-007, 011, 012, 016, 017, 019, 020)."""

import math
from dataclasses import replace

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cl_strategies import COLUMNS, H_C, HEADER, Move, changed, columns, operations, refusal
from splintercam.cl import MoveKind, make_operation
from splintercam.foundation import Context

# The ctx fixture is a frozen value, the same for every example.
_SETTINGS = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])


@pytest.mark.req("REQ-CL-016", "REQ-CL-019")
@_SETTINGS
@given(operations())
def test_valid_operations_pass_unchanged_and_read_only(ctx: Context, moves: list[Move]) -> None:
    produced = columns(moves)
    held = make_operation(HEADER, produced, ctx).moves
    for name in COLUMNS:
        np.testing.assert_array_equal(getattr(held, name), getattr(produced, name))
        assert not getattr(held, name).flags.writeable
        assert getattr(held, name) is not getattr(produced, name)


@pytest.mark.req("REQ-CL-007", "REQ-CL-020")
@_SETTINGS
@given(operations(), st.data())
def test_a_value_that_is_not_finite_names_its_move(
    ctx: Context, moves: list[Move], data: st.DataObject
) -> None:
    move = data.draw(st.integers(1, len(moves) - 1))
    axis = data.draw(st.integers(0, 2))
    value = data.draw(st.sampled_from((math.nan, math.inf, -math.inf)))
    with pytest.raises(ValueError, match=refusal("REQ-CL-007", move)):
        make_operation(HEADER, changed(columns(moves), "end_mm", (move, axis), value), ctx)


@pytest.mark.req("REQ-CL-011", "REQ-CL-020")
@_SETTINGS
@given(operations(), st.data())
def test_a_rapid_ending_below_its_link_height_names_its_move(
    ctx: Context, moves: list[Move], data: st.DataObject
) -> None:
    rapids = [i for i, m in enumerate(moves) if m.kind == MoveKind.RAPID]
    move = data.draw(st.sampled_from(rapids))
    raised = math.nextafter(moves[move].end[2], math.inf)
    with pytest.raises(ValueError, match=refusal("REQ-CL-011", move)):
        make_operation(HEADER, changed(columns(moves), "link_height_mm", move, raised), ctx)


@pytest.mark.req("REQ-CL-012", "REQ-CL-020")
@_SETTINGS
@given(operations(), st.data())
def test_a_last_rapid_below_the_clearance_height_is_named(
    ctx: Context, moves: list[Move], data: st.DataObject
) -> None:
    # The last rapid lowered, with its link height.
    last = len(moves) - 1
    lower = H_C - data.draw(st.integers(1, 2**12)) * 2.0**-10
    lowered = changed(columns(moves), "end_mm", (last, 2), lower)
    with pytest.raises(ValueError, match=refusal("REQ-CL-012", last)):
        make_operation(HEADER, changed(lowered, "link_height_mm", last, lower), ctx)


@pytest.mark.req("REQ-CL-016", "REQ-CL-020")
@_SETTINGS
@given(operations(with_arc=True), st.data())
def test_an_arc_given_a_longer_sweep_names_its_move(
    ctx: Context, moves: list[Move], data: st.DataObject
) -> None:
    # The sweep lengthened by 3 eps_len / r, so the end lies 3 eps_len along the circle from
    # where the sweep reaches; no other move changes.
    arcs = [i for i, m in enumerate(moves) if m.kind == MoveKind.ARC]
    move = data.draw(st.sampled_from(arcs))
    centre, start = moves[move].centre, moves[move - 1].end
    radius = math.sqrt((start[0] - centre[0]) ** 2 + (start[1] - centre[1]) ** 2)
    sweep = moves[move].sweep
    longer = sweep + math.copysign(3 * ctx.tolerances.length_eps_mm / radius, sweep)
    with pytest.raises(ValueError, match=refusal("REQ-CL-016", move)):
        make_operation(HEADER, changed(columns(moves), "sweep_rad", move, longer), ctx)


_HEADER_BREAKERS: tuple[tuple[str, object], ...] = (
    ("name", "a b"), ("note", ("\x00",)), ("tool_number", 0), ("point_number", -1),
    ("axial_offset_mm", -1.0), ("spindle_rpm", math.nan), ("tol_mm", 0.0),
    ("feed_classes", (("cut", -1.0),)), ("clearance_height_mm", math.inf),
)  # fmt: skip


@pytest.mark.req("REQ-CL-017", "REQ-CL-020")
@_SETTINGS
@given(operations(), st.sampled_from(_HEADER_BREAKERS))
def test_a_broken_header_field_is_named_before_any_move(
    ctx: Context, moves: list[Move], breaker: tuple[str, object]
) -> None:
    field, value = breaker
    header = replace(HEADER, **{field: value})
    pattern = refusal("REQ-CL-017", name=header.name) + f": header field {field}"
    with pytest.raises(ValueError, match=pattern):
        make_operation(header, columns(moves), ctx)
