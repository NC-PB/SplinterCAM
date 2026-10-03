# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the signed area of a loop (research 01, Area and orientation; tests 3 and 19)."""

import math
from fractions import Fraction
from typing import Any

import numpy as np
import pytest

import geometry2d_oracles as oracle
from geometry2d_checks import codes, loop, polygon, reversed_loop
from splintercam import _kernels
from splintercam.foundation import TOLERANCE_DEFAULTS, Context
from splintercam.geometry2d import CurveRows, signed_area

NAN = math.nan
# The square [0, 10]² with its right side replaced by an outward semicircle about (10, 5).
BULGED_SQUARE = [
    [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0],
    [10.0, 0.0, 10.0, 10.0, 10.0, 5.0, math.pi],
    [10.0, 10.0, 0.0, 10.0, NAN, NAN, 0.0],
    [0.0, 10.0, 0.0, 0.0, NAN, NAN, 0.0],
]


def _area(loop_rows: CurveRows, ctx: Context) -> float:
    result = signed_area(loop_rows, ctx)
    assert result.value is not None, result.diagnostics
    assert result.diagnostics == ()
    return result.value


@pytest.mark.req("REQ-G2D-001", "REQ-G2D-128")
def test_a_ccw_square_has_positive_area(ctx: Context) -> None:
    assert _area(polygon([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)], ctx), ctx) == 100.0


@pytest.mark.req("REQ-G2D-128")
@pytest.mark.parametrize("sweep", [math.tau, -math.tau])
def test_research_test_3_full_circle(ctx: Context, sweep: float) -> None:
    circle = loop([[10.0, 0.0, 10.0, 0.0, 0.0, 0.0, sweep]], ctx)
    assert _area(circle, ctx) == pytest.approx(math.copysign(100 * math.pi, sweep), rel=1e-12)


@pytest.mark.req("REQ-G2D-001", "REQ-G2D-002", "REQ-G2D-128")
def test_research_test_3_square_with_a_semicircle(ctx: Context) -> None:
    area = _area(loop(BULGED_SQUARE, ctx), ctx)
    assert area == pytest.approx(100 + 12.5 * math.pi, rel=1e-12)
    assert area == pytest.approx(139.270, abs=5e-4)
    reversed_area = _area(loop(reversed_loop(BULGED_SQUARE), ctx), ctx)
    assert reversed_area == pytest.approx(-area, rel=1e-12)


@pytest.mark.req("REQ-G2D-133")
@pytest.mark.parametrize(("width", "kept"), [(1e-7, False), (1e-5, True), (1e-3, True)])
def test_research_test_19_degenerate_loop(ctx: Context, width: float, kept: bool) -> None:
    strip = polygon([(0.0, 0.0), (10.0, 0.0), (10.0, width), (0.0, width)], ctx)
    result = signed_area(strip, ctx)
    if kept:
        assert result.value == pytest.approx(10 * width, rel=1e-9)
        assert codes(result) == []
    else:
        assert result.value is None
        assert codes(result) == ["LOOP_DEGENERATE"]


@pytest.mark.req("REQ-G2D-133")
@pytest.mark.parametrize(("width", "kept"), [(1.99e-6, False), (2.01e-6, True)])
def test_the_degenerate_limit_is_eps_len_times_the_length(
    ctx: Context, width: float, kept: bool
) -> None:
    # A 1 by w strip: A = w, L = 2 + 2w, so |A| <= eps_len·L while w <= about 2·eps_len.
    assert ctx.tolerances.length_eps_mm == 1e-6
    strip = polygon([(0.0, 0.0), (1.0, 0.0), (1.0, width), (0.0, width)], ctx)
    assert (signed_area(strip, ctx).value is not None) is kept


@pytest.mark.req("REQ-G2D-128")
def test_more_than_one_loop_is_a_programming_error(ctx: Context) -> None:
    one = polygon([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)], ctx)
    two = CurveRows(
        np.vstack([one.rows, one.rows]),
        np.arange(6, dtype=np.int64),
        np.array([0, 3], dtype=np.int64),
    )
    with pytest.raises(ValueError, match="one loop"):
        signed_area(two, ctx)


def _exact_flag(ctx: Context, loop_rows: CurveRows, monkeypatch: pytest.MonkeyPatch) -> bool:
    seen: list[bool] = []
    kernel = _kernels.geometry2d.loop_area

    def spy(*args: Any) -> None:
        seen.append(bool(args[3]))  # loop_area(rows, centre_x, centre_y, exact, out)
        kernel(*args)

    monkeypatch.setattr(_kernels.geometry2d, "loop_area", spy)
    signed_area(loop_rows, ctx)
    (flag,) = seen
    return flag


@pytest.mark.req("REQ-G2D-131", "REQ-G2D-132", "REQ-G2D-230")
def test_the_float_limits_are_declared_parameters() -> None:
    assert TOLERANCE_DEFAULTS["area_float_max_vertices"].default == 10**6
    assert TOLERANCE_DEFAULTS["area_float_max_half_extent_mm"].default == 3355


@pytest.mark.req("REQ-G2D-131", "REQ-G2D-132")
@pytest.mark.parametrize(("half_extent", "exact"), [(3355.0, False), (3355.0 + 2.0**-40, True)])
def test_a_loop_just_above_the_extent_limit_sums_exactly(
    ctx: Context, monkeypatch: pytest.MonkeyPatch, half_extent: float, exact: bool
) -> None:
    e = half_extent
    square = polygon([(-e, -e), (e, -e), (e, e), (-e, e)], ctx)
    assert _exact_flag(ctx, square, monkeypatch) is exact


@pytest.mark.req("REQ-G2D-131", "REQ-G2D-132")
@pytest.mark.parametrize(("n", "exact"), [(10**6, False), (10**6 + 1, True)])
def test_a_loop_just_above_the_vertex_limit_sums_exactly(
    ctx: Context, monkeypatch: pytest.MonkeyPatch, n: int, exact: bool
) -> None:
    angles = np.linspace(0.0, math.tau, n, endpoint=False)
    points = np.column_stack((np.cos(angles), np.sin(angles)))
    rows = np.column_stack((points, np.roll(points, -1, axis=0), np.full((n, 2), NAN), np.zeros(n)))
    loop_rows = CurveRows(rows, np.arange(n, dtype=np.int64), np.zeros(1, np.int64))
    assert _exact_flag(ctx, loop_rows, monkeypatch) is exact


@pytest.mark.req("REQ-G2D-130", "REQ-G2D-132")
def test_the_exact_sum_is_the_area_of_the_translated_loop(
    ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Far from the origin and beyond the extent limit: the polygon part is summed exactly after
    # the translation to the centre of the bounding box, so the result is the exact area of the
    # translated vertices, rounded once, within a rounding unit.
    rng = np.random.default_rng(7)
    # 5000 vertices: enough for the expansion to be compressed along the way.
    raw = rng.uniform(-4000.0, 4000.0, size=(5000, 2)) + np.array([1.0e4, -3.0e4])
    points = [(float(x), float(y)) for x, y in raw]
    xs, ys = raw[:, 0], raw[:, 1]
    cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
    translated = [(x - cx, y - cy) for x, y in points]
    exact = oracle.polygon_area(translated)
    area = _area(polygon(points, ctx), ctx)
    assert abs(Fraction(area) - exact) <= Fraction(math.ulp(float(exact)))


@pytest.mark.req("REQ-G2D-231")
def test_the_area_is_bit_identical_when_repeated(ctx: Context) -> None:
    bulged = loop(BULGED_SQUARE, ctx)
    first = signed_area(bulged, ctx)
    assert signed_area(bulged, ctx) == first
