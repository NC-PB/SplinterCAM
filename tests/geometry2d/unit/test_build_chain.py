# SPDX-License-Identifier: Apache-2.0
"""Unit tests of the flattened open chain of a profile (research 01, Flattening with a known
error side; D-025)."""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes
from splintercam.foundation import Context
from splintercam.geometry2d import AirSide, Arc, Line, build_chain, flatten

NAN = math.nan
# A line, a CCW half circle (centre left of it) and a CW half circle (centre right of it).
LINE = [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0]
CCW = [10.0, 0.0, 20.0, 0.0, 15.0, 0.0, math.pi]
CW = [20.0, 0.0, 30.0, 0.0, 25.0, 0.0, -math.pi]
IDS = np.array([4, 5, 6], dtype=np.int64)


def _rows(*rows: list[float]) -> NDArray[np.float64]:
    return np.array(rows, dtype=np.float64)


def _curve(row: list[float]) -> Line | Arc:
    x0, y0, x1, y1, cx, cy, sweep = row
    return Line((x0, y0), (x1, y1)) if sweep == 0.0 else Arc((x0, y0), (x1, y1), (cx, cy), sweep)


@pytest.mark.req("REQ-G2D-117", "REQ-G2D-125", "REQ-G2D-127")
@pytest.mark.parametrize("side", list(AirSide))
def test_every_arc_is_flattened_into_the_side_the_tool_works_on(
    ctx: Context, side: AirSide
) -> None:
    result = build_chain(_rows(LINE, CCW, CW), IDS, side, ctx)
    assert result.ok, result.diagnostics
    chain = result.value
    assert chain is not None
    assert chain.extra_clearance_mm == 0.0
    # Each row as `flatten` gives it within t_flat on that side, each joint once, bit for bit.
    t_flat = ctx.tolerances.flatten_tol_mm
    alone = [flatten(_curve(row), t_flat, side, ctx) for row in (LINE, CCW, CW)]
    np.testing.assert_array_equal(
        chain.points, np.vstack([p[:-1] for p in alone] + [alone[-1][-1:]])
    )
    counts = [p.shape[0] - 1 for p in alone]
    assert chain.source_ids.tolist() == np.repeat(IDS, counts).tolist()
    # Tool on the left: the CCW arc (centre on the left) inscribed, the CW arc circumscribed.
    for row, centre_left in ((CCW, True), (CW, False)):
        on_arc = (chain.points[:, 0] > row[0]) & (chain.points[:, 0] < row[2])
        radius = np.hypot(*(chain.points[on_arc] - row[4:6]).T)
        inscribed = centre_left == (side is AirSide.LEFT)
        assert np.all(radius <= 5.0 + 1e-9) if inscribed else np.all(radius > 5.0)


@pytest.mark.req("REQ-G2D-234")
def test_a_closed_chain_is_accepted(ctx: Context) -> None:
    back = [30.0, 0.0, 0.0, 0.0, 15.0, 0.0, math.pi]
    result = build_chain(
        _rows(LINE, CCW, CW, back), np.arange(4, dtype=np.int64), AirSide.RIGHT, ctx
    )
    assert result.ok, result.diagnostics
    assert result.value is not None
    np.testing.assert_array_equal(result.value.points[0], result.value.points[-1])
    assert result.value.source_ids.shape == (result.value.points.shape[0] - 1,)


@pytest.mark.req("REQ-G2D-234")
def test_a_one_row_chain_has_two_points(ctx: Context) -> None:
    result = build_chain(_rows(LINE), np.array([9], np.int64), AirSide.LEFT, ctx)
    assert result.value is not None
    assert result.value.points.tolist() == [[0.0, 0.0], [10.0, 0.0]]
    assert result.value.source_ids.tolist() == [9]


BROKEN: dict[str, tuple[list[list[float]], str]] = {
    "a line with a centre (REQ-G2D-190)": ([[0, 0, 10, 0, 5, 0, 0.0]], "CURVE_INVALID"),
    "an arc with a NaN centre (REQ-G2D-191)": ([[10, 0, 20, 0, NAN, 0, math.pi]], "CURVE_INVALID"),
    "a sweep over 2π (REQ-G2D-191)": ([[5, 0, 5, 0, 0, 0, 7.0]], "CURVE_INVALID"),
    "an arc off its circle (REQ-G2D-192)": ([[10, 0, 20, 0, 15, 1, math.pi]], "ARC_INCONSISTENT"),
    "an infinite end (REQ-G2D-193)": ([[0, 0, math.inf, 0, NAN, NAN, 0.0]], "CURVE_INVALID"),
    "a gap between rows": ([LINE, [10.0, 1e-12, 20, 0, NAN, NAN, 0.0]], "CURVE_INVALID"),
}


@pytest.mark.req("REQ-G2D-234", "REQ-G2D-188")
@pytest.mark.parametrize("name", list(BROKEN))
def test_broken_rows_are_rejected_with_the_code_of_their_rule(ctx: Context, name: str) -> None:
    rows, code = BROKEN[name]
    result = build_chain(
        np.array(rows, dtype=np.float64), np.arange(len(rows), dtype=np.int64), AirSide.LEFT, ctx
    )
    assert result.value is None
    assert codes(result) == [code]


@pytest.mark.req("REQ-G2D-234", "REQ-G2D-188")
@pytest.mark.parametrize(
    ("rows", "ids"),
    [
        (np.empty((0, 7)), np.empty(0, np.int64)),  # the empty chain
        (_rows(LINE).astype(np.float32), np.array([1], np.int64)),
        (_rows(LINE)[:, :6], np.array([1], np.int64)),
        (_rows(LINE), np.array([1], np.int32)),
        (_rows(LINE), np.array([1, 2], np.int64)),
    ],
)
def test_wrong_shapes_dtypes_and_the_empty_chain_are_curve_invalid(
    ctx: Context, rows: NDArray[np.generic], ids: NDArray[np.generic]
) -> None:
    result = build_chain(rows, ids, AirSide.LEFT, ctx)
    assert result.value is None
    assert codes(result) == ["CURVE_INVALID"]


@pytest.mark.req("REQ-G2D-231")
def test_the_same_chain_twice_is_the_same_bit_for_bit(ctx: Context) -> None:
    first, second = (
        build_chain(_rows(LINE, CCW, CW), IDS, AirSide.LEFT, ctx).value for _ in range(2)
    )
    assert first is not None
    assert second is not None
    assert first.points.tobytes() == second.points.tobytes()
    assert first.source_ids.tobytes() == second.source_ids.tobytes()
