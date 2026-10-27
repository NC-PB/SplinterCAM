# SPDX-License-Identifier: Apache-2.0
"""Unit tests for `make_operation`'s arc rules: full and tiny circles, planar arcs, the circle and
the sweep (REQ-CL-014, 015, 016, 021)."""

import math

import pytest

from cl_strategies import (
    HEADER,
    NAN,
    Move,
    arc,
    changed,
    columns,
    framed,
    full_circle,
    profile_moves,
    refusal,
)
from geometry2d_checks import with_length_eps
from splintercam.cl import make_operation
from splintercam.foundation import Context

_ARC = 4  # the index of the one cut move in `framed`
_FIRST_ARC = 6  # the first fillet of research 22 test 1's record
_EPS = 2.0**-20  # a dyadic eps_len, so the boundary ends below are exact


def _quarter(end: tuple[float, float], sweep: float = math.pi / 2) -> list[Move]:
    # A quarter arc of radius 5 about the origin from (5, 0), its end given.
    return framed([arc((*end, -1.0), (0.0, 0.0), sweep)], (5.0, 0.0))


def _along(factor: float, eps: float) -> tuple[float, float]:
    # The quarter's end moved along the circle by factor · eps_len.
    angle = math.pi / 2 + factor * eps / 5.0
    return (5.0 * math.cos(angle), 5.0 * math.sin(angle))


@pytest.mark.req("REQ-CL-014")
@pytest.mark.parametrize("sweep", [math.tau, -math.tau])
def test_full_circles_with_end_at_start_pass(sweep: float, ctx: Context) -> None:
    operation = make_operation(HEADER, columns(full_circle(sweep)), ctx)
    assert operation.moves.sweep_rad[_ARC] == sweep


@pytest.mark.req("REQ-CL-014")
def test_a_sweep_above_2pi_is_refused(ctx: Context) -> None:
    above = math.nextafter(math.tau, math.inf)
    for sweep in (above, -above):
        with pytest.raises(ValueError, match=refusal("REQ-CL-014", _ARC)):
            make_operation(HEADER, columns(full_circle(sweep)), ctx)


@pytest.mark.req("REQ-CL-014")
def test_a_full_circle_must_end_exactly_at_its_start(ctx: Context) -> None:
    for end in ((10.0, 1e-7), (math.nextafter(10.0, 0.0), 0.0)):
        with pytest.raises(ValueError, match=refusal("REQ-CL-014", _ARC)):
            make_operation(HEADER, columns(full_circle(-math.tau, end)), ctx)


@pytest.mark.req("REQ-CL-014")
def test_a_tiny_arc_is_refused(ctx: Context) -> None:
    # Sweep 1e-7 rad at r = 5: the end lies 5e-7 mm from the start, within eps_len.
    end = (5.0 * math.cos(1e-7), 5.0 * math.sin(1e-7))
    with pytest.raises(ValueError, match=refusal("REQ-CL-014", _ARC)):
        make_operation(HEADER, columns(_quarter(end, 1e-7)), ctx)


@pytest.mark.req("REQ-CL-014")
@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("sweep_rad", 0.0),
        ("sweep_rad", -0.0),
        ("sweep_rad", NAN),
        ("sweep_rad", math.inf),
        ("centre_mm", (NAN, 5.0)),
        ("centre_mm", (5.0, math.inf)),
    ],
)
def test_an_arc_needs_a_finite_centre_and_a_sweep(column: str, value: object, ctx: Context) -> None:
    broken = changed(columns(profile_moves()), column, _FIRST_ARC, value)
    with pytest.raises(ValueError, match=refusal("REQ-CL-014", _FIRST_ARC)):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-015")
def test_an_arc_is_planar(ctx: Context) -> None:
    z = columns(profile_moves()).end_mm[_FIRST_ARC, 2]
    for end_z in (math.nextafter(z, 0.0), z - 1.0):
        broken = changed(columns(profile_moves()), "end_mm", (_FIRST_ARC, 2), end_z)
        with pytest.raises(ValueError, match=refusal("REQ-CL-015", _FIRST_ARC)):
            make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-016")
def test_a_consistent_quarter_passes(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    for end in ((0.0, 5.0), (0.0, 5.0 + 0.5 * eps), (0.0, 5.0 - 0.5 * eps), _along(0.5, eps)):
        make_operation(HEADER, columns(_quarter(end)), ctx)
    make_operation(HEADER, columns(_quarter(_along(-0.5, eps))), ctx)


@pytest.mark.req("REQ-CL-016")
def test_an_end_off_the_circle_or_the_sweep_is_refused(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    ends = [(0.0, 5.0 + 2 * eps), (0.0, 5.0 - 2 * eps), _along(1.5, eps), _along(-1.5, eps)]
    for end in ends:
        with pytest.raises(ValueError, match=refusal("REQ-CL-016", _ARC)):
            make_operation(HEADER, columns(_quarter(end)), ctx)


@pytest.mark.req("REQ-CL-016")
def test_a_ccw_quarter_given_a_cw_sweep_is_refused(ctx: Context) -> None:
    with pytest.raises(ValueError, match=refusal("REQ-CL-016", _ARC)):
        make_operation(HEADER, columns(_quarter((0.0, 5.0), -math.pi / 2)), ctx)


@pytest.mark.req("REQ-CL-016")
def test_an_arc_with_its_centre_at_its_start_is_refused(ctx: Context) -> None:
    moves = framed([arc((0.0, 5.0, -1.0), (5.0, 0.0), math.pi / 2)], (5.0, 0.0))
    with pytest.raises(ValueError, match=refusal("REQ-CL-016", _ARC)):
        make_operation(HEADER, columns(moves), ctx)


@pytest.mark.req("REQ-CL-016")
def test_a_fillet_end_0_01_off_its_circle_is_refused(ctx: Context) -> None:
    # Research 22 test 1 with the first fillet's end moved 0.01 mm outwards (SPEC, Example parts).
    broken = changed(columns(profile_moves()), "end_mm", (_FIRST_ARC, 0), -5.01)
    with pytest.raises(ValueError, match=refusal("REQ-CL-016", _FIRST_ARC)):
        make_operation(HEADER, broken, ctx)


@pytest.mark.req("REQ-CL-021", "REQ-CL-016")
def test_pinned_arcs_at_the_radial_boundary(ctx: Context) -> None:
    # Exact: with eps_len 2^-20, |P1 - C| - r is eps_len to the bit, then one ulp beyond. CI runs
    # this on every platform it tests; the decision must not change (D-055 tier 1).
    exact = with_length_eps(ctx, _EPS)
    for end in ((0.0, 5.0 + _EPS), (0.0, 5.0 - _EPS)):
        make_operation(HEADER, columns(_quarter(end)), exact)
    for end in ((0.0, math.nextafter(5.0 + _EPS, math.inf)), (0.0, 5.0 + 2 * _EPS)):
        with pytest.raises(ValueError, match=refusal("REQ-CL-016", _ARC)):
            make_operation(HEADER, columns(_quarter(end)), exact)


@pytest.mark.req("REQ-CL-021", "REQ-CL-014")
def test_pinned_tiny_arc_at_eps_len(ctx: Context) -> None:
    # A half circle of radius eps_len / 2 + 2^-40 about (5 + r, 0): its end lies 2r from its
    # start, just above eps_len, and passes; its radius is above eps_len only if r is, so this
    # also pins REQ-CL-016's radius rule: refused there, not by the tiny-arc rule.
    exact = with_length_eps(ctx, _EPS)
    r = _EPS / 2 + 2.0**-40
    moves = framed([arc((5.0 + 2 * r, 0.0, -1.0), (5.0 + r, 0.0), math.pi)], (5.0, 0.0))
    with pytest.raises(ValueError, match=refusal("REQ-CL-016", _ARC)):
        make_operation(HEADER, columns(moves), exact)
    at_eps = framed([arc((5.0 + _EPS, 0.0, -1.0), (5.0 + _EPS / 2, 0.0), math.pi)], (5.0, 0.0))
    with pytest.raises(ValueError, match=refusal("REQ-CL-014", _ARC)):
        make_operation(HEADER, columns(at_eps), exact)
