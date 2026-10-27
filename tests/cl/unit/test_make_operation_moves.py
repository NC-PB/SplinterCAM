# SPDX-License-Identifier: Apache-2.0
"""Unit tests for `make_operation`'s columns, kinds, starts, feeds and heights (REQ-CL-003 to
013)."""

import math
from dataclasses import replace

import numpy as np
import pytest

from cl_strategies import (
    CUT,
    H_C,
    H_R,
    HEADER,
    NAN,
    PLUNGE,
    P,
    S,
    arc,
    changed,
    columns,
    line,
    profile_moves,
    rapid,
    refusal,
)
from splintercam.cl import NO_FEED_CLASS, ClMoves, MoveKind, Role, make_operation
from splintercam.foundation import Context

_COLUMNS = ("kind", "role", "end_mm", "centre_mm", "sweep_rad", "feed_class", "link_height_mm")


def _profile() -> ClMoves:
    return columns(profile_moves())


# Indexes into research 22 test 1's record: the first pass starts at move 2.
_DOWN, _PLUNGE, _LEAD_IN, _FIRST_ARC, _UP = 2, 3, 4, 6, 15


@pytest.mark.req("REQ-CL-003")
def test_the_profile_record_has_the_seven_columns(ctx: Context) -> None:
    moves = make_operation(HEADER, _profile(), ctx).moves
    dtypes = [getattr(moves, name).dtype for name in _COLUMNS]
    assert dtypes == [np.int8, np.int8, *[np.float64] * 3, np.int64, np.float64]
    shapes = [getattr(moves, name).shape for name in _COLUMNS]
    assert shapes == [(44,), (44,), (44, 3), (44, 2), (44,), (44,), (44,)]
    rapid_rows = moves.kind == MoveKind.RAPID
    assert np.isnan(moves.centre_mm[moves.kind != MoveKind.ARC]).all()
    assert (moves.sweep_rad[moves.kind != MoveKind.ARC] == 0.0).all()
    assert (moves.feed_class[rapid_rows] == NO_FEED_CLASS).all()
    assert np.isnan(moves.link_height_mm[~rapid_rows]).all()
    assert np.isnan(moves.end_mm[0, :2]).all()
    assert moves.sweep_rad[_FIRST_ARC] == -math.pi / 2


@pytest.mark.req("REQ-CL-004")
@pytest.mark.parametrize("column", _COLUMNS)
def test_a_column_of_the_wrong_type_is_refused(column: str, ctx: Context) -> None:
    good = _profile()
    array = getattr(good, column)
    other = np.float32 if array.dtype == np.float64 else np.int16
    for wrong in (array.tolist(), array.astype(other), array[..., np.newaxis]):
        with pytest.raises(ValueError, match=refusal("REQ-CL-004") + f": column {column}"):
            make_operation(HEADER, replace(good, **{column: wrong}), ctx)


@pytest.mark.req("REQ-CL-004")
@pytest.mark.parametrize("column", _COLUMNS[1:])
def test_row_counts_must_agree(column: str, ctx: Context) -> None:
    good = _profile()
    broken = replace(good, **{column: getattr(good, column)[:-1]})
    with pytest.raises(ValueError, match=refusal("REQ-CL-004") + f": column {column}"):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-004")
def test_an_operation_without_moves_is_refused(ctx: Context) -> None:
    with pytest.raises(ValueError, match=refusal("REQ-CL-004") + ": column kind"):
        make_operation(HEADER, columns([]), ctx)


@pytest.mark.req("REQ-CL-005")
@pytest.mark.parametrize(
    ("column", "move", "value"),
    [
        ("kind", _UP, 3),  # not a MoveKind
        ("role", _LEAD_IN, 4),  # not a Role
        ("role", _DOWN, Role.APPROACH),  # a RAPID that is not a LINK
        ("role", _PLUNGE, Role.LINK),  # a LINE link (D-087: later)
        ("role", _FIRST_ARC, Role.LINK),
    ],
)
def test_kinds_and_roles(column: str, move: int, value: int, ctx: Context) -> None:
    broken = changed(_profile(), column, move, value)
    with pytest.raises(ValueError, match=refusal("REQ-CL-005", move)):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-006")
@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("kind", MoveKind.LINE),
        ("end_mm", (0.0, NAN, H_C)),
        ("end_mm", (NAN, 0.0, H_C)),
        ("end_mm", (NAN, NAN, NAN)),
        ("end_mm", (NAN, NAN, math.inf)),
    ],
)
def test_the_first_move_is_a_rapid_along_the_axis(column: str, value: object, ctx: Context) -> None:
    broken = _profile()
    if value == MoveKind.LINE:  # a valid LINE in every other respect
        broken = changed(changed(broken, "role", 0, Role.CUT), "feed_class", 0, CUT)
        broken = changed(broken, "link_height_mm", 0, NAN)
    broken = changed(broken, column, 0, value)
    with pytest.raises(ValueError, match=refusal("REQ-CL-006", 0)):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-007")
@pytest.mark.parametrize("value", [NAN, math.inf, -math.inf])
@pytest.mark.parametrize(("move", "axis"), [(1, 0), (1, 1), (_LEAD_IN, 2), (43, 1)])
def test_an_end_that_is_not_finite_is_refused(
    move: int, axis: int, value: float, ctx: Context
) -> None:
    broken = changed(_profile(), "end_mm", (move, axis), value)
    with pytest.raises(ValueError, match=refusal("REQ-CL-007", move)):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-008")
def test_the_second_move_is_not_a_line_or_an_arc(ctx: Context) -> None:
    after = [rapid(NAN, NAN, H_C, H_C)]
    cases = [
        line(*P, H_C),
        arc((*P, H_C), (P[0], 0.0), math.pi),
    ]
    for second in cases:
        moves = columns([*after, second, rapid(*P, H_C, H_C)])
        with pytest.raises(ValueError, match=refusal("REQ-CL-008", 1)):
            make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-009")
@pytest.mark.parametrize(
    ("move", "value"),
    [(_DOWN, PLUNGE), (_PLUNGE, NO_FEED_CLASS), (_LEAD_IN, 2), (_FIRST_ARC, -2)],
)
def test_feed_classes_by_kind(move: int, value: int, ctx: Context) -> None:
    broken = changed(_profile(), "feed_class", move, value)
    with pytest.raises(ValueError, match=refusal("REQ-CL-009", move)):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-010")
@pytest.mark.parametrize(
    ("move", "value"),
    [(_DOWN, NAN), (_DOWN, math.inf), (_PLUNGE, H_R), (_FIRST_ARC, math.inf)],
)
def test_link_heights_by_kind(move: int, value: float, ctx: Context) -> None:
    broken = changed(_profile(), "link_height_mm", move, value)
    with pytest.raises(ValueError, match=refusal("REQ-CL-010", move)):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-011", "REQ-CL-012")
def test_the_profile_record_is_accepted(ctx: Context) -> None:
    operation = make_operation(HEADER, _profile(), ctx)
    assert operation.header is HEADER
    assert operation.moves.kind[-1] == MoveKind.RAPID
    assert operation.moves.end_mm[-1, 2] == H_C


@pytest.mark.req("REQ-CL-011")
def test_a_rapid_in_the_plane_below_its_link_height_is_refused(ctx: Context) -> None:
    # In the plane at h_r - 0.001 from above P to above S, with link height h_r.
    head = [rapid(NAN, NAN, H_C, H_C), rapid(*P, H_C, H_C), rapid(*P, H_R - 0.001, H_R - 0.001)]
    moves = columns([*head, rapid(*S, H_R - 0.001, H_R), rapid(*S, H_C, H_C)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-011", 3)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-011")
def test_a_rapid_from_p_to_s_below_its_link_height_is_refused(ctx: Context) -> None:
    head = [rapid(NAN, NAN, H_C, H_C), rapid(*P, H_C, H_C), rapid(*P, H_R, H_R)]
    moves = columns([*head, rapid(*S, H_R, H_C), rapid(*S, H_C, H_C)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-011", 3)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-011")
def test_the_rapid_up_from_p_one_ulp_off_counts_as_a_move_in_the_plane(ctx: Context) -> None:
    # DEC-CL-004: the rapid up from P after the retract starts at z_1 < h_c; with x one ulp off P
    # it changes x and raises. With x equal to P it passes (the profile record).
    off = math.nextafter(P[0], math.inf)
    broken = changed(_profile(), "end_mm", (_UP, 0), off)
    with pytest.raises(ValueError, match=refusal("REQ-CL-011", _UP)):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-011")
def test_move_1_counts_as_a_move_in_the_plane(ctx: Context) -> None:
    # Move 1 starts at (unknown, unknown, 5): below a link height of 6 it raises.
    moves = columns([rapid(NAN, NAN, H_C, H_C), rapid(*P, 6.0, 6.0), rapid(*P, H_C, H_C)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-011", 1)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-012")
def test_a_diagonal_move_1_down_from_the_tool_change_is_refused(ctx: Context) -> None:
    moves = columns([rapid(NAN, NAN, H_C, H_C), rapid(*P, H_R, H_R), rapid(*P, H_C, H_C)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-012", 1)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-012")
def test_move_0_below_the_clearance_height_is_refused(ctx: Context) -> None:
    # Move 1's link height 4, so it does not start below it (REQ-CL-011 comes first).
    moves = columns([rapid(NAN, NAN, 4.0, 4.0), rapid(*P, H_C, 4.0)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-012", 0)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-012")
def test_the_operation_ends_with_a_rapid_at_the_clearance_height(ctx: Context) -> None:
    no_last_rapid = profile_moves()[:-1]
    low_last_rapid = [*no_last_rapid, rapid(*P, 4.0, 4.0)]
    for moves, last in ((no_last_rapid, 42), (low_last_rapid, 43)):
        with pytest.raises(ValueError, match=refusal("REQ-CL-012", last)):
            make_operation(HEADER, columns(moves), ctx)


@pytest.mark.req("REQ-CL-013")
@pytest.mark.parametrize(
    ("column", "move", "value"),
    [
        ("centre_mm", _DOWN, (0.0, 0.0)),
        ("centre_mm", _LEAD_IN, (NAN, 0.0)),
        ("sweep_rad", _DOWN, math.pi),
        ("sweep_rad", _LEAD_IN, -1e-300),
    ],
)
def test_rapids_and_lines_have_no_centre_or_sweep(
    column: str, move: int, value: object, ctx: Context
) -> None:
    broken = changed(_profile(), column, move, value)
    with pytest.raises(ValueError, match=refusal("REQ-CL-013", move)):
        make_operation(HEADER, broken, ctx)
