# SPDX-License-Identifier: Apache-2.0
"""Unit tests for curve rows at the kernel boundary (research 01, Kernel arrays; test 20)."""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes
from splintercam.foundation import Context
from splintercam.geometry2d import curve_rows

NAN = math.nan
# Research 01, test 20's valid loops: a one-row full circle, then a line and an arc closing it.
CIRCLE = [5.0, 0.0, 5.0, 0.0, 0.0, 0.0, math.tau]
LINE = [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0]
HALF = [10.0, 0.0, 0.0, 0.0, 5.0, 0.0, math.pi]


def _valid() -> tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64]]:
    rows = np.array([CIRCLE, LINE, HALF], dtype=np.float64)
    return rows, np.array([7, 8, 9], dtype=np.int64), np.array([0, 1], dtype=np.int64)


@pytest.mark.req("REQ-G2D-188", "REQ-G2D-196")
def test_a_one_row_circle_and_a_two_row_loop_are_valid(ctx: Context) -> None:
    rows, ids, starts = _valid()
    result = curve_rows(rows, ids, starts, ctx)
    assert result.ok, result.diagnostics
    assert result.value is not None
    np.testing.assert_array_equal(result.value.rows, rows)
    assert result.value.ids.tolist() == [7, 8, 9]
    assert result.value.row_starts.tolist() == [0, 1]


@pytest.mark.req("REQ-G2D-189")
def test_negative_zero_sweep_is_a_line(ctx: Context) -> None:
    rows, ids, starts = _valid()
    rows[1, 6] = -0.0
    assert curve_rows(rows, ids, starts, ctx).ok


def _rejected(ctx: Context, rows: NDArray[np.float64], code: str = "CURVE_INVALID") -> None:
    _, ids, starts = _valid()
    result = curve_rows(rows, ids, starts, ctx)
    assert result.value is None
    assert codes(result) == [code]


@pytest.mark.req("REQ-G2D-190")
@pytest.mark.parametrize("column", [4, 5])
def test_line_row_with_a_centre_is_curve_invalid(ctx: Context, column: int) -> None:
    rows, _, _ = _valid()
    rows[1, column] = 5.0
    _rejected(ctx, rows)


@pytest.mark.req("REQ-G2D-191")
@pytest.mark.parametrize(("column", "value"), [(4, NAN), (5, math.inf), (6, 7.0), (6, -7.0)])
def test_arc_row_with_a_bad_centre_or_sweep_is_curve_invalid(
    ctx: Context, column: int, value: float
) -> None:
    rows, _, _ = _valid()
    rows[2, column] = value
    _rejected(ctx, rows)


@pytest.mark.req("REQ-G2D-192")
def test_arc_row_breaking_the_arc_rule_is_arc_inconsistent(ctx: Context) -> None:
    # Peter, 2026-10-02: ARC_INCONSISTENT, where research 01 test 20 says CURVE_INVALID.
    rows, ids, starts = _valid()
    rows[2, 6] = -math.pi  # a CW half from (10, 0) to (0, 0) bulges the other way: still fits
    assert curve_rows(rows, ids, starts, ctx).ok
    rows[2, 6] = math.pi / 2  # a quarter cannot reach (0, 0) from (10, 0)
    _rejected(ctx, rows, "ARC_INCONSISTENT")


@pytest.mark.req("REQ-G2D-193")
@pytest.mark.parametrize(("row", "column"), [(1, 0), (1, 3), (2, 1), (0, 6)])
@pytest.mark.parametrize("value", [NAN, math.inf, -math.inf])
def test_other_non_finite_values_are_curve_invalid(
    ctx: Context, row: int, column: int, value: float
) -> None:
    rows, _, _ = _valid()
    rows[row, column] = value
    _rejected(ctx, rows)


@pytest.mark.req("REQ-G2D-194")
def test_a_gap_between_rows_is_curve_invalid(ctx: Context) -> None:
    rows, _, _ = _valid()
    rows[1, 2] = math.nextafter(10.0, math.inf)  # the line ends one rounding unit short
    _rejected(ctx, rows)


@pytest.mark.req("REQ-G2D-194")
def test_continuity_is_bit_for_bit(ctx: Context) -> None:
    rows, _, _ = _valid()
    rows[2, 3] = -0.0  # the arc ends at (0, -0.0), the line starts at (0, 0)
    _rejected(ctx, rows)


@pytest.mark.req("REQ-G2D-194")
def test_an_open_loop_is_curve_invalid(ctx: Context) -> None:
    rows = np.array([LINE, [10.0, 0.0, 0.0, 1.0, NAN, NAN, 0.0]])
    result = curve_rows(rows, np.array([1, 2]), np.array([0]), ctx)
    assert codes(result) == ["CURVE_INVALID"]


@pytest.mark.req("REQ-G2D-197")
@pytest.mark.parametrize(
    ("rows", "ids", "starts"),
    [
        (np.zeros((2, 6)), np.array([1, 2]), np.array([0])),  # rows not (m, 7)
        (np.array([CIRCLE], dtype=np.float32), np.array([1]), np.array([0])),  # rows not float64
        (np.array([CIRCLE]), np.array([1], dtype=np.int32), np.array([0])),  # ids not int64
        (np.array([CIRCLE]), np.array([1, 2]), np.array([0])),  # one ID per row
        (np.array([CIRCLE]), np.array([1]), np.array([0], dtype=np.int32)),  # starts not int64
        (np.array([CIRCLE]), np.array([1]), np.array([], dtype=np.int64)),  # no loop
        (np.array([CIRCLE, CIRCLE]), np.array([1, 2]), np.array([1])),  # not starting at 0
        (np.array([CIRCLE, CIRCLE]), np.array([1, 2]), np.array([0, 0, 1])),  # empty loop
        (np.array([CIRCLE, CIRCLE]), np.array([1, 2]), np.array([0, 2])),  # beyond the rows
        (np.array([CIRCLE]), np.array([1]), np.array([[0]])),  # starts not one-dimensional
    ],
)
def test_wrong_shapes_dtypes_and_row_starts_are_curve_invalid(
    ctx: Context, rows: NDArray[np.float64], ids: NDArray[np.int64], starts: NDArray[np.int64]
) -> None:
    assert codes(curve_rows(rows, ids, starts, ctx)) == ["CURVE_INVALID"]


@pytest.mark.req("REQ-G2D-201")
def test_arrays_are_contiguous_read_only_copies(ctx: Context) -> None:
    rows, ids, starts = _valid()
    wide = np.zeros((3, 14))
    wide[:, ::2] = rows  # a strided view of the same values
    result = curve_rows(wide[:, ::2], ids, starts, ctx)
    assert result.value is not None
    pairs = ((result.value.rows, wide), (result.value.ids, ids), (result.value.row_starts, starts))
    for array, given in pairs:
        assert array.flags.c_contiguous
        assert not array.flags.writeable
        assert not np.shares_memory(array, given)
    np.testing.assert_array_equal(result.value.rows, rows)
