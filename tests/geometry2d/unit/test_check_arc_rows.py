# SPDX-License-Identifier: Apache-2.0
"""Unit tests for `check_arc_rows`, the status of curve rows as given (REQ-G2D-248)."""

import math

import numpy as np
import pytest

from geometry2d_checks import with_length_eps
from splintercam.foundation import Context
from splintercam.geometry2d import Arc, RowStatus, check_arc_rows, make_arc

# A dyadic eps_len, so the boundary rows below are exact: |P1 - C| - r is eps_len to the bit.
_EPS = 2.0**-20
_NAN = math.nan


def _status(rows: list[list[float]], ctx: Context) -> list[int]:
    return [int(code) for code in check_arc_rows(np.array(rows, dtype=np.float64), ctx)]


def _quarter(p1: tuple[float, float], sweep: float = math.pi / 2) -> list[float]:
    # A quarter arc of radius 5 about the origin from (5, 0), its end given.
    return [5.0, 0.0, *p1, 0.0, 0.0, sweep]


@pytest.mark.req("REQ-G2D-248")
def test_the_radial_rule_holds_at_eps_len(ctx: Context) -> None:
    exact = with_length_eps(ctx, _EPS)
    rows = [
        _quarter((0.0, 5.0)),
        _quarter((0.0, 5.0 + _EPS)),  # |P1 - C| - r = eps_len exactly: accepted
        _quarter((0.0, 5.0 - _EPS)),
        _quarter((0.0, 5.0 + 2 * _EPS)),  # beyond it
        _quarter((0.0, 5.0 - 2 * _EPS)),
        _quarter((0.0, math.nextafter(5.0 + _EPS, math.inf))),  # one ulp beyond
    ]
    ok, bad = RowStatus.OK, RowStatus.ARC_INCONSISTENT
    assert _status(rows, exact) == [ok, ok, ok, bad, bad, bad]


@pytest.mark.req("REQ-G2D-248")
def test_a_nearly_closed_arc_is_checked_as_written(ctx: Context) -> None:
    # make_arc closes it into a full circle (REQ-G2D-049); check_arc_rows builds nothing and
    # finds its end 1.8·eps_len along the circle from where the sweep reaches.
    eps = ctx.tolerances.length_eps_mm
    p0, p1, centre, sweep = (5.0, 0.0), (5.0, 0.9 * eps), (0.0, 0.0), math.tau - 0.9 * eps / 5
    closed = make_arc(p0, p1, centre, sweep, ctx).value
    assert closed is not None
    assert closed[0] == Arc(p0, p0, centre, math.tau)
    assert _status([[*p0, *p1, *centre, sweep]], ctx) == [RowStatus.ARC_INCONSISTENT]


@pytest.mark.req("REQ-G2D-248")
def test_the_angle_rule_holds_at_eps_len_over_r(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm

    def along(factor: float) -> list[float]:
        # P1 moved along the circle by factor · eps_len from the end the sweep reaches.
        angle = math.pi / 2 + factor * eps / 5.0
        return _quarter((5.0 * math.cos(angle), 5.0 * math.sin(angle)))

    rows = [along(0.5), along(-0.5), along(1.5), along(-1.5)]
    ok, bad = RowStatus.OK, RowStatus.ARC_INCONSISTENT
    assert _status(rows, ctx) == [ok, ok, bad, bad]


@pytest.mark.req("REQ-G2D-248")
def test_a_radius_at_eps_len_is_invalid(ctx: Context) -> None:
    exact = with_length_eps(ctx, _EPS)
    above = math.nextafter(_EPS, math.inf)
    rows = [
        [_EPS, 0.0, 0.0, _EPS, 0.0, 0.0, math.pi / 2],  # r = eps_len: make_arc makes it a line
        [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, math.tau],  # r = 0
        # P1 far off the tiny circle: still invalid (make_arc says ARC_INCONSISTENT; the
        # radius rule comes first, DEC-G2D-045)
        [_EPS, 0.0, 0.0, 1.0, 0.0, 0.0, math.pi / 2],
        [above, 0.0, 0.0, above, 0.0, 0.0, math.pi / 2],  # one ulp above: an arc
    ]
    invalid = RowStatus.CURVE_INVALID
    assert _status(rows, exact) == [invalid, invalid, invalid, RowStatus.OK]


@pytest.mark.req("REQ-G2D-248")
def test_line_rows_need_finite_ends_only(ctx: Context) -> None:
    rows = [
        [0.0, 0.0, 3.0, 4.0, _NAN, _NAN, 0.0],
        [0.0, 0.0, 3.0, 4.0, _NAN, _NAN, -0.0],
        [0.0, 0.0, 3.0, 4.0, 7.0, -2.0, 0.0],  # the centre of a line is not read
        [1.0, 1.0, 1.0, 1.0, _NAN, _NAN, 0.0],  # a zero-length line
        [0.0, 0.0, math.inf, 4.0, _NAN, _NAN, 0.0],
        [0.0, _NAN, 3.0, 4.0, _NAN, _NAN, 0.0],
    ]
    ok, invalid = RowStatus.OK, RowStatus.CURVE_INVALID
    assert _status(rows, ctx) == [ok, ok, ok, ok, invalid, invalid]


@pytest.mark.req("REQ-G2D-248")
def test_full_circles(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    above = math.nextafter(math.tau, math.inf)
    rows = [
        [5.0, 0.0, 5.0, 0.0, 0.0, 0.0, math.tau],
        [5.0, 0.0, 5.0, 0.0, 0.0, 0.0, -math.tau],
        [5.0, 0.0, 5.0, 0.0, 0.0, 0.0, above],  # the double above 2π
        [5.0, 0.0, 5.0, 0.0, 0.0, 0.0, -above],
        [5.0, 0.0, 5.0, 0.5 * eps, 0.0, 0.0, math.tau],  # the end within eps_len: the rules hold
        [5.0, 0.0, 5.0, 2.0 * eps, 0.0, 0.0, math.tau],
    ]
    ok, invalid = RowStatus.OK, RowStatus.CURVE_INVALID
    assert _status(rows, ctx) == [ok, ok, invalid, invalid, ok, RowStatus.ARC_INCONSISTENT]


@pytest.mark.req("REQ-G2D-248")
def test_an_arc_is_checked_in_the_direction_it_is_written(ctx: Context) -> None:
    rows = [
        _quarter((0.0, 5.0)),  # CCW quarter
        [0.0, 5.0, 5.0, 0.0, 0.0, 0.0, -math.pi / 2],  # the same arc reversed
        _quarter((0.0, 5.0), -math.pi / 2),  # the CCW quarter given a CW sweep: a 3/4 turn
        _quarter((0.0, -5.0), -math.pi / 2),  # CW quarter
        _quarter((0.0, -5.0), -3 * math.pi / 2),  # wrong: that end is a quarter away
        _quarter((0.0, 5.0), -3 * math.pi / 2),  # the CW 3/4 turn to (0, 5)
    ]
    ok, bad = RowStatus.OK, RowStatus.ARC_INCONSISTENT
    assert _status(rows, ctx) == [ok, ok, bad, ok, bad, ok]


@pytest.mark.req("REQ-G2D-248")
@pytest.mark.parametrize(
    "row",
    [
        [5.0, 0.0, 0.0, 5.0, _NAN, 0.0, math.pi / 2],
        [5.0, 0.0, 0.0, 5.0, 0.0, math.inf, math.pi / 2],
        [5.0, 0.0, 0.0, 5.0, 0.0, 0.0, _NAN],
        [5.0, 0.0, 0.0, 5.0, 0.0, 0.0, math.inf],
        [5.0, 0.0, 0.0, 5.0, 0.0, 0.0, 7.0],  # |sweep| > 2π
        [_NAN, 0.0, 0.0, 5.0, 0.0, 0.0, math.pi / 2],
        [5.0, 0.0, 0.0, -math.inf, 0.0, 0.0, math.pi / 2],
    ],
)
def test_arcs_with_values_out_of_range_are_invalid(ctx: Context, row: list[float]) -> None:
    assert _status([row], ctx) == [RowStatus.CURVE_INVALID]


@pytest.mark.req("REQ-G2D-248")
def test_the_rows_are_not_changed_and_each_row_has_its_own_status(ctx: Context) -> None:
    rows = np.array(
        [
            _quarter((0.0, 5.0)),
            [0.0, 0.0, 1.0, 0.0, _NAN, _NAN, 0.0],
            _quarter((0.0, 6.0)),
            _quarter((0.0, 5.0), 7.0),
        ]
    )
    given = rows.copy()
    status = check_arc_rows(rows, ctx)
    assert status.dtype == np.int8
    assert list(status) == [0, 0, 2, 1]
    assert np.array_equal(rows, given, equal_nan=True)
    assert check_arc_rows(np.empty((0, 7)), ctx).shape == (0,)


@pytest.mark.req("REQ-G2D-247", "REQ-G2D-248")
def test_wrong_shapes_raise(ctx: Context) -> None:
    with pytest.raises(ValueError, match="rows"):
        check_arc_rows(np.zeros((2, 6)), ctx)
    with pytest.raises(ValueError, match="rows"):
        check_arc_rows(np.zeros(7), ctx)
    with pytest.raises(ValueError, match="rows"):
        check_arc_rows(np.zeros((2, 7), dtype=np.float32), ctx)  # pyright: ignore[reportArgumentType] (the error under test)
    with pytest.raises(ValueError, match="rows"):
        check_arc_rows([[0.0] * 7], ctx)  # pyright: ignore[reportArgumentType] (the error under test)
