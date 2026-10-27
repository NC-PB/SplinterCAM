# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the setup's record and its copies (REQ-CL-001, 018, 019)."""

import math
from dataclasses import replace

import numpy as np
import pytest

from cl_strategies import (
    HEADER,
    changed,
    columns,
    full_circle,
    profile_moves,
    refusal,
)
from splintercam.cl import ClOperation, make_cl_data, make_operation
from splintercam.foundation import Context

_FIRST_ARC = 6


def _operation(name: str, ctx: Context) -> ClOperation:
    return make_operation(replace(HEADER, name=name), columns(profile_moves()), ctx)


@pytest.mark.req("REQ-CL-001")
def test_operations_and_moves_keep_their_order(ctx: Context) -> None:
    circle = make_operation(replace(HEADER, name="B"), columns(full_circle(math.tau)), ctx)
    given = (_operation("A", ctx), circle, _operation("C", ctx))
    data = make_cl_data(3, given, ctx)
    assert data.work_offset == 3
    assert [op.header.name for op in data.operations] == ["A", "B", "C"]
    for held, original in zip(data.operations, given, strict=True):
        np.testing.assert_array_equal(held.moves.kind, original.moves.kind)
        np.testing.assert_array_equal(held.moves.end_mm, original.moves.end_mm)


@pytest.mark.req("REQ-CL-018", "REQ-CL-020")
def test_the_work_offset_is_at_least_1(ctx: Context) -> None:
    with pytest.raises(ValueError, match=r"^cl data: REQ-CL-018: work offset 0"):
        make_cl_data(0, (_operation("A", ctx),), ctx)


@pytest.mark.req("REQ-CL-018", "REQ-CL-020")
def test_there_is_an_operation(ctx: Context) -> None:
    with pytest.raises(ValueError, match=r"^cl data: REQ-CL-018: no operation"):
        make_cl_data(1, (), ctx)


@pytest.mark.req("REQ-CL-018", "REQ-CL-020")
def test_operation_names_are_unique(ctx: Context) -> None:
    operations = (_operation("A", ctx), _operation("B", ctx), _operation("A", ctx))
    with pytest.raises(ValueError, match=refusal("REQ-CL-018", name="A") + ": operation 2"):
        make_cl_data(1, operations, ctx)


@pytest.mark.req("REQ-CL-018", "REQ-CL-020")
def test_an_operation_built_directly_is_checked_again(ctx: Context) -> None:
    broken = changed(columns(profile_moves()), "end_mm", (_FIRST_ARC, 0), -5.01)
    direct = ClOperation(replace(HEADER, name="B"), broken)
    # The broken operation comes before a repeated name: operations are checked first.
    operations = (_operation("A", ctx), direct, _operation("A", ctx))
    with pytest.raises(ValueError, match=refusal("REQ-CL-016", _FIRST_ARC, name="B")):
        make_cl_data(1, operations, ctx)


@pytest.mark.req("REQ-CL-018")
def test_the_held_operation_is_the_rebuilt_one(ctx: Context) -> None:
    direct = ClOperation(HEADER, columns(profile_moves()))
    held = make_cl_data(1, (direct,), ctx).operations[0]
    assert held is not direct
    assert held.moves is not direct.moves
    assert held.header == direct.header


@pytest.mark.req("REQ-CL-019")
def test_make_operation_holds_read_only_copies(ctx: Context) -> None:
    produced = columns(profile_moves())
    held = make_operation(HEADER, produced, ctx).moves
    produced.end_mm[5, 0] = 99.0
    produced.kind[5] = 0
    assert held.end_mm[5, 0] == 5.0
    assert held.kind[5] == 1
    for name in ("kind", "role", "end_mm", "centre_mm", "sweep_rad", "feed_class"):
        assert not getattr(held, name).flags.writeable
    assert not held.link_height_mm.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        held.end_mm[5, 0] = 99.0


@pytest.mark.req("REQ-CL-019")
def test_make_cl_data_holds_read_only_copies(ctx: Context) -> None:
    produced = columns(profile_moves())
    held = make_cl_data(1, (ClOperation(HEADER, produced),), ctx).operations[0].moves
    produced.sweep_rad[_FIRST_ARC] = 1.0
    assert held.sweep_rad[_FIRST_ARC] == -math.pi / 2
    assert not held.sweep_rad.flags.writeable
