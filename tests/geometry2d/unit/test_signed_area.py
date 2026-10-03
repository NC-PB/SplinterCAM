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
from splintercam.foundation import Context, Severity
from splintercam.geometry2d import Arc, CurveRows, arc_from_bulge, signed_area

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
        assert result.diagnostics[0].severity is Severity.WARNING


@pytest.mark.req("REQ-G2D-133")
@pytest.mark.parametrize(("width", "kept"), [(1.99e-6, False), (2.01e-6, True)])
def test_the_degenerate_limit_is_eps_len_times_the_length(
    ctx: Context, width: float, kept: bool
) -> None:
    # A 1 by w strip: A = w, L = 2 + 2w, so |A| <= eps_len·L while w <= about 2·eps_len.
    assert ctx.tolerances.length_eps_mm == 1e-6
    strip = polygon([(0.0, 0.0), (1.0, 0.0), (1.0, width), (0.0, width)], ctx)
    assert (signed_area(strip, ctx).value is not None) is kept


@pytest.mark.req("REQ-G2D-133")
@pytest.mark.parametrize(("sagitta", "kept"), [(2.25e-6, False), (3.75e-6, True)])
def test_arc_lengths_count_in_the_degenerate_limit(
    ctx: Context, sagitta: float, kept: bool
) -> None:
    # The chord (0, 0)-(2, 0) and a shallow arc back: A ≈ (4/3)·sagitta, L ≈ 4, so eps_len·L ≈
    # 4e-6. A = 3e-6 is degenerate only if the arc's length counts; A = 5e-6 is kept.
    arc = arc_from_bulge((2.0, 0.0), (0.0, 0.0), sagitta, ctx).value
    assert isinstance(arc, Arc)
    rows = [[0.0, 0.0, 2.0, 0.0, NAN, NAN, 0.0], [*arc.p0, *arc.p1, *arc.centre, arc.sweep_rad]]
    assert (signed_area(loop(rows, ctx), ctx).value is not None) is kept


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


def _kernel_call(
    ctx: Context, loop_rows: CurveRows, monkeypatch: pytest.MonkeyPatch
) -> tuple[float, float, bool]:
    """The centre and the exact flag `signed_area` passes to the kernel."""
    seen: list[tuple[float, float, bool]] = []
    kernel = _kernels.geometry2d.loop_area

    def spy(*args: Any) -> tuple[float, float]:
        seen.append((args[1], args[2], bool(args[3])))  # rows, centre_x, centre_y, exact
        return kernel(*args)

    monkeypatch.setattr(_kernels.geometry2d, "loop_area", spy)
    signed_area(loop_rows, ctx)
    (call,) = seen
    return call


@pytest.mark.req("REQ-G2D-131", "REQ-G2D-132")
@pytest.mark.parametrize(("half_extent", "exact"), [(3355.0, False), (3355.0 + 2.0**-40, True)])
def test_a_loop_just_above_the_extent_limit_sums_exactly(
    ctx: Context, monkeypatch: pytest.MonkeyPatch, half_extent: float, exact: bool
) -> None:
    e = half_extent
    square = polygon([(-e, -e), (e, -e), (e, e), (-e, e)], ctx)
    assert _kernel_call(ctx, square, monkeypatch)[2] is exact


@pytest.mark.req("REQ-G2D-131", "REQ-G2D-132")
@pytest.mark.parametrize("wide_in_x", [True, False])
def test_either_axis_beyond_the_extent_limit_sums_exactly(
    ctx: Context, monkeypatch: pytest.MonkeyPatch, wide_in_x: bool
) -> None:
    a, b = (3356.0, 1.0) if wide_in_x else (1.0, 3356.0)
    rectangle = polygon([(-a, -b), (a, -b), (a, b), (-a, b)], ctx)
    assert _kernel_call(ctx, rectangle, monkeypatch)[2]


def test_the_float_limits_keep_research_01s_bound_below_eps_len() -> None:
    # n·u·(√2·E·L + 3E²) <= eps_len·L at the limits, for the shortest closed loop L = 4E.
    n, e, eps = 10**6, 3355.0, 1e-6
    length = 4 * e
    assert n * 2.0**-53 * (math.sqrt(2) * e * length + 3 * e * e) <= eps * length


@pytest.mark.req("REQ-G2D-131", "REQ-G2D-132")
def test_the_arc_precondition_keeps_the_whole_bound_below_eps_len() -> None:
    # DEC-G2D-016: arcs add at most 40u·r·min(1, φ²) per mm of loop length, r·min(1, φ²) <= 10^7 mm.
    u, n, e, eps = 2.0**-53, 10**6, 3355.0, 1e-6
    arcs_per_mm = 40 * u * 1e7
    float_path = n * u * (math.sqrt(2) * e + 3 * e * e / (4 * e))  # per mm, at L = 4E
    exact_path = 2 * u * 1e9  # the translation, per mm, at E = 10^9 mm
    assert float_path + arcs_per_mm <= 0.9 * eps
    assert exact_path + arcs_per_mm <= 0.3 * eps


@pytest.mark.req("REQ-G2D-131", "REQ-G2D-132")
@pytest.mark.parametrize(("n", "exact"), [(10**6, False), (10**6 + 1, True)])
def test_a_loop_just_above_the_vertex_limit_sums_exactly(
    ctx: Context, monkeypatch: pytest.MonkeyPatch, n: int, exact: bool
) -> None:
    angles = np.linspace(0.0, math.tau, n, endpoint=False)
    points = np.column_stack((np.cos(angles), np.sin(angles)))
    rows = np.column_stack((points, np.roll(points, -1, axis=0), np.full((n, 2), NAN), np.zeros(n)))
    loop_rows = CurveRows(rows, np.arange(n, dtype=np.int64), np.zeros(1, np.int64))
    assert _kernel_call(ctx, loop_rows, monkeypatch)[2] is exact


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
    loop_rows = polygon(points, ctx)
    assert _kernel_call(ctx, loop_rows, monkeypatch)[:2] == (cx, cy)  # REQ-G2D-130
    area = _area(loop_rows, ctx)
    assert abs(Fraction(area) - exact) <= Fraction(math.ulp(float(exact)))


@pytest.mark.req("REQ-G2D-128", "REQ-G2D-132")
def test_the_exact_path_sums_arcs_too(ctx: Context) -> None:
    # Half-extent 4000 mm, beyond the limit: a full circle and the bulged square scaled up.
    circle = loop([[4000.0, 0.0, 4000.0, 0.0, 0.0, 0.0, math.tau]], ctx)
    assert _area(circle, ctx) == pytest.approx(math.pi * 4000.0**2, rel=1e-12)
    scaled = [[v * 400 if i < 6 else v for i, v in enumerate(row)] for row in BULGED_SQUARE]
    assert _area(loop(scaled, ctx), ctx) == pytest.approx(
        400**2 * (100 + 12.5 * math.pi), rel=1e-12
    )


@pytest.mark.req("REQ-G2D-231")
@pytest.mark.parametrize("scale", [1.0, 400.0])  # the float and the exact path
def test_the_area_is_bit_identical_when_repeated(ctx: Context, scale: float) -> None:
    rows = [[v * scale if i < 6 else v for i, v in enumerate(row)] for row in BULGED_SQUARE]
    bulged = loop(rows, ctx)
    first = signed_area(bulged, ctx)
    assert signed_area(bulged, ctx) == first
