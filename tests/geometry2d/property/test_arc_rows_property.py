# SPDX-License-Identifier: Apache-2.0
"""Property tests: the array forms equal the per-curve functions bit for bit, row by row, in
mixed batches (REQ-G2D-243 to 246, 248; DEC-G2D-044: bit identity is the requirement, so these
compare exact floats on purpose)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from geometry2d_checks import codes, curve_row, same_bits, scalar_row
from splintercam.foundation import TOLERANCE_DEFAULTS, Context, Result
from splintercam.geometry2d import (
    Arc,
    Curve,
    Line,
    RowStatus,
    arc_from_bulge,
    bounding_box,
    check_arc_rows,
    make_arc,
    row_boxes,
    rows_from_bulges,
    rows_from_sweeps,
)

# Coordinates on a 2^-20 mm grid, so the exact predicates stay inside their range (AGENTS.md).
# -0.0 too: Python's min and max keep the first of 0.0 and -0.0, which the kernel must copy.
coordinate = st.one_of(st.just(-0.0), st.integers(-(2**30), 2**30).map(lambda k: k / 2**20))
size = st.floats(1e-3, 1e3)
# Ends below, between and above eps_len/2 and eps_len, from the declared default (REQ-FND-008).
_EPS = TOLERANCE_DEFAULTS["length_eps_mm"].default
_NEAR_CLOSED = [0.0, 0.48 * _EPS, 0.95 * _EPS, 1.5 * _EPS, 1.9 * _EPS]  # 1.5: make_arc's line
Case = tuple[tuple[float, float], tuple[float, float], float]
edge_bulges = st.sampled_from([0.0, -0.0, 1e-12, -1e-9, 1.0, -1.0, 1e6, math.nan, math.inf])


Point = tuple[float, float]


@st.composite
def ends(draw: st.DrawFn) -> tuple[Point, Point]:
    p0 = (draw(coordinate), draw(coordinate))
    if draw(st.integers(0, 4)) == 0:  # equal ends, ends around eps_len/2 and eps_len
        # For a large bulge (2π - |φ|)·r is about the chord: these offsets put the nearly
        # closed rule (REQ-G2D-049) below, between and above its two bounds.
        p1 = (p0[0] + draw(st.sampled_from(_NEAR_CLOSED)), p0[1])
    else:
        p1 = (draw(coordinate), draw(coordinate))
    return p0, p1


@st.composite
def bulge_case(draw: st.DrawFn) -> Case:
    p0, p1 = draw(ends())
    bulge = draw(st.one_of(edge_bulges, size.map(lambda b: b), size.map(lambda b: -b)))
    return p0, p1, bulge


def _arrays(
    cases: list[Case],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p0 = np.array([c[0] for c in cases], dtype=np.float64).reshape(-1, 2)
    p1 = np.array([c[1] for c in cases], dtype=np.float64).reshape(-1, 2)
    return p0, p1, np.array([c[2] for c in cases], dtype=np.float64)


@pytest.mark.req("REQ-G2D-243", "REQ-G2D-246")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(cases=st.lists(bulge_case(), min_size=1, max_size=12))
def test_rows_from_bulges_equal_arc_from_bulge(ctx: Context, cases: list[Case]) -> None:
    built = rows_from_bulges(*_arrays(cases), ctx)
    for i, (p0, p1, bulge) in enumerate(cases):
        expected, status = scalar_row(arc_from_bulge(p0, p1, bulge, ctx))
        assert built.status[i] == status, (i, p0, p1, bulge)
        assert same_bits(built.rows[i], expected), (i, built.rows[i], expected)


@pytest.mark.req("REQ-G2D-244", "REQ-G2D-246")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    end_points=ends(),
    sweep=st.floats(-math.tau, math.tau, exclude_min=True, exclude_max=True),
)
def test_rows_from_sweeps_keep_the_sweep_on_the_bulge_centre(
    ctx: Context, end_points: tuple[Point, Point], sweep: float
) -> None:
    p0, p1 = end_points
    assume(sweep != 0.0)
    via_bulge = arc_from_bulge(p0, p1, math.tan(sweep / 4), ctx)
    # The oracle takes the bulge form's centre; skip the rare case where the bulge form alone is
    # inconsistent and has none.
    assume("ARC_INCONSISTENT" not in codes(via_bulge))
    built = rows_from_sweeps(np.array([p0]), np.array([p1]), np.array([sweep]), ctx)
    expected, status = scalar_row(via_bulge)
    if isinstance(via_bulge.value, Arc):
        rebuilt = make_arc(p0, p1, via_bulge.value.centre, sweep, ctx)
        curves = rebuilt.value
        expected, status = scalar_row(Result(curves[0]) if curves else rebuilt)  # pyright: ignore[reportArgumentType]
    assert built.status[0] == status
    assert same_bits(built.rows[0], expected), (built.rows[0], expected)


@st.composite
def curve(draw: st.DrawFn) -> Curve:
    p0 = (draw(coordinate), draw(coordinate))
    if draw(st.booleans()):
        return Line(p0, (draw(coordinate), draw(coordinate)))
    centre = (draw(coordinate), draw(coordinate))
    if draw(st.integers(0, 7)) == 0:
        return Arc(p0, p0, centre, draw(st.sampled_from([math.tau, -math.tau])))
    # P1 on the circle within rounding, at the angle the sweep reaches, or anywhere: the box
    # takes unchecked rows and only reads the octants of P0 and P1 and the sweep, so rows whose
    # P1 contradicts the sweep must give bounding_box's answer too.
    sweep = draw(st.floats(-math.tau, math.tau, exclude_min=True, exclude_max=True))
    assume(sweep != 0.0)
    a0 = math.atan2(p0[1] - centre[1], p0[0] - centre[0])
    r = math.dist(p0, centre)
    p1 = (centre[0] + r * math.cos(a0 + sweep), centre[1] + r * math.sin(a0 + sweep))
    if draw(st.booleans()):
        p1 = (draw(coordinate), draw(coordinate))
    return Arc(p0, p1, centre, sweep)


@pytest.mark.req("REQ-G2D-245", "REQ-G2D-246")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(curves=st.lists(curve(), min_size=1, max_size=12))
def test_row_boxes_equal_bounding_box(ctx: Context, curves: list[Curve]) -> None:
    rows = np.array([curve_row(c) for c in curves])
    boxes = row_boxes(rows, ctx)
    for i, c in enumerate(curves):
        box = bounding_box(c, ctx)
        expected = np.array([box.x_min_mm, box.y_min_mm, box.x_max_mm, box.y_max_mm])
        assert same_bits(boxes[i], expected), (i, c, boxes[i], expected)


def _make_arc_status(c: Arc, ctx: Context) -> int | None:
    # make_arc's verdict on the row as given; CURVE_INVALID for r <= eps_len, which make_arc
    # never returns as an arc (DEC-G2D-045); None where it closes the arc into a full circle.
    if c.radius_mm <= ctx.tolerances.length_eps_mm:
        return int(RowStatus.CURVE_INVALID)
    result = make_arc(c.p0, c.p1, c.centre, c.sweep_rad, ctx)
    if result.value is None:
        return int(RowStatus[codes(result)[0]])
    return int(RowStatus.OK) if result.value == (c,) else None


@pytest.mark.req("REQ-G2D-248", "REQ-G2D-246")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(curves=st.lists(curve(), min_size=1, max_size=12))
def test_check_arc_rows_agrees_with_make_arc(ctx: Context, curves: list[Curve]) -> None:
    # The generator's arcs end on their circle, at the sweep's end within rounding, or anywhere,
    # so batches mix consistent and inconsistent rows with lines and full circles.
    rows = np.array([curve_row(c) for c in curves])
    status = check_arc_rows(rows, ctx)
    for i, c in enumerate(curves):
        expected = int(RowStatus.OK) if isinstance(c, Line) else _make_arc_status(c, ctx)
        if expected is not None:
            assert status[i] == expected, (i, c, status[i])
