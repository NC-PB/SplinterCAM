# SPDX-License-Identifier: Apache-2.0
"""Unit tests for plan 0007's links: rapids in the plane at the clearance height, none below the
retract height (REQ-CL-022; AQ-018 (c); research 10, Method)."""

import math

import pytest

from cl_strategies import (
    H_C,
    H_R,
    HEADER,
    NAN,
    P,
    S,
    columns,
    line,
    profile_moves,
    rapid,
    refusal,
)
from splintercam.cl import Role, make_operation
from splintercam.foundation import Context

_TOOL_CHANGE = rapid(NAN, NAN, H_C, H_C)


@pytest.mark.req("REQ-CL-022")
def test_the_profile_record_passes(ctx: Context) -> None:
    # Research 22 test 1: rapids in the plane at h_c, the descents at P end at h_r exactly.
    make_operation(HEADER, columns(profile_moves()), ctx)


@pytest.mark.req("REQ-CL-022")
def test_aq_018s_rapid_into_the_stock_is_refused(ctx: Context) -> None:
    # AQ-018: link heights copied from the target z, so REQ-CL-011 holds; move 3 is a diagonal
    # G0 from the approach point into the stock at cut depth.
    z = -10.0 / 3.0
    moves = [
        rapid(NAN, NAN, 50.0, 50.0),
        rapid(-10.0, 0.0, H_C, H_C),
        rapid(-10.0, 0.0, H_R, H_R),
        rapid(20.0, 0.0, z, z),
        line(60.0, 0.0, z),
        rapid(60.0, 0.0, 50.0, 50.0),
    ]
    with pytest.raises(ValueError, match=refusal("REQ-CL-022", 3)):
        make_operation(HEADER, columns(moves), ctx)


@pytest.mark.req("REQ-CL-022")
def test_a_rapid_in_the_plane_at_the_retract_height_is_refused(ctx: Context) -> None:
    # From above P to above S at h_r, link height h_r: allowed by REQ-CL-011, not in plan 0007.
    head = [_TOOL_CHANGE, rapid(*P, H_C, H_C), rapid(*P, H_R, H_R)]
    moves = columns([*head, rapid(*S, H_R, H_R), rapid(*S, H_C, H_C)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-022", 3)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-022")
def test_a_rapid_in_the_plane_one_ulp_below_the_clearance_height_is_refused(ctx: Context) -> None:
    # Exact (DEC-CL-004): from P at h_c to S one ulp below h_c, with its link height there.
    below = math.nextafter(H_C, 0.0)
    head = [_TOOL_CHANGE, rapid(*P, H_C, H_C)]
    moves = columns([*head, rapid(*S, below, below), rapid(*S, H_C, H_C)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-022", 2)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-022")
def test_a_rapid_in_the_plane_starting_below_the_clearance_height_is_refused(
    ctx: Context,
) -> None:
    # Up from P at h_r to above S at h_c, link height h_r: it starts at its link height
    # (REQ-CL-011 holds) but below h_c, moving in the plane.
    head = [_TOOL_CHANGE, rapid(*P, H_C, H_C), rapid(*P, H_R, H_R)]
    moves = columns([*head, rapid(*S, H_C, H_R)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-022", 3)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-022")
def test_a_vertical_rapid_below_the_retract_height_is_refused(ctx: Context) -> None:
    # At P straight down to one ulp below h_r, with its link height there.
    below = math.nextafter(H_R, 0.0)
    head = [_TOOL_CHANGE, rapid(*P, H_C, H_C), rapid(*P, below, below)]
    plunge = line(*P, -1.0, Role.APPROACH)
    moves = columns([*head, plunge, rapid(*P, H_C, H_C)])
    with pytest.raises(ValueError, match=refusal("REQ-CL-022", 2)):
        make_operation(HEADER, moves, ctx)
