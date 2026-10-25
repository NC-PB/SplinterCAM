# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the array forms of the arc constructions and the bounding box (DEC-G2D-044)."""

import math

import numpy as np
import pytest

from geometry2d_checks import curve_row, same_bits, scalar_row
from splintercam.foundation import Context
from splintercam.geometry2d import (
    Arc,
    Line,
    RowStatus,
    arc_from_bulge,
    bounding_box,
    make_arc,
    row_boxes,
    rows_from_bulges,
    rows_from_sweeps,
)


def _points(values: list[tuple[float, float]]) -> np.ndarray:
    return np.array(values, dtype=np.float64).reshape(-1, 2)


_FAR_P0 = (-2193.8145353255927, 2084.6024216233964)
_FAR_P1 = (-2027.5405122503425, 447.3620202011575)
_FAR_BULGE = -4.201558904263802e-09


@pytest.mark.req("REQ-G2D-244")
def test_an_inconsistent_sweep_is_reported(ctx: Context) -> None:
    sweep = 4 * math.atan(_FAR_BULGE)
    built = rows_from_sweeps(_points([_FAR_P0]), _points([_FAR_P1]), np.array([sweep]), ctx)
    assert built.status[0] == RowStatus.ARC_INCONSISTENT
    assert np.isnan(built.rows[0]).all()


def _bulge_rows(
    cases: list[tuple[tuple[float, float], tuple[float, float], float]], ctx: Context
) -> tuple[np.ndarray, np.ndarray]:
    p0 = _points([case[0] for case in cases])
    p1 = _points([case[1] for case in cases])
    bulges = np.array([case[2] for case in cases], dtype=np.float64)
    built = rows_from_bulges(p0, p1, bulges, ctx)
    return built.rows, built.status


@pytest.mark.req("REQ-G2D-243")
def test_bulges_give_the_rows_of_arc_from_bulge(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    cases = [
        ((0.0, 0.0), (2.0, 0.0), 1.0),  # research 01 test 8: semicircles
        ((0.0, 0.0), (2.0, 0.0), -1.0),
        ((0.0, 0.0), (2.0, 0.0), math.tan(math.pi / 8)),
        ((0.0, 0.0), (1.0, 0.0), 0.0),  # lines (REQ-G2D-051)
        ((0.0, 0.0), (1.0, 0.0), -0.0),
        ((0.0, 0.0), (1.0, 0.0), 1e-9),
        ((0.0, 0.0), (eps / 2, 0.0), 1e6),  # nearly closed: a full circle (REQ-G2D-049)
        ((0.0, 0.0), (1.5 * eps, 0.0), 2.0),  # r = 0.9375·eps_len: make_arc's line (REQ-G2D-047)
        ((5.0, 5.0), (5.0, 5.0), 1.0),  # a bulge on a zero chord (REQ-G2D-050)
        ((0.0, 0.0), (1.0, math.nan), 0.5),  # non-finite values
        ((0.0, 0.0), (1.0, 0.0), math.inf),
        # r near 1e11 mm, beyond the radius precondition (DEC-G2D-019): the scalar's
        # ARC_INCONSISTENT, found by a search
        (_FAR_P0, _FAR_P1, _FAR_BULGE),
    ]
    rows, status = _bulge_rows(cases, ctx)
    for i, (p0, p1, bulge) in enumerate(cases):
        expected, expected_status = scalar_row(arc_from_bulge(p0, p1, bulge, ctx))
        assert status[i] == expected_status, i
        assert same_bits(rows[i], expected), (i, rows[i], expected)
    assert list(status[-4:]) == [RowStatus.CURVE_INVALID] * 3 + [RowStatus.ARC_INCONSISTENT]
    assert np.isnan(rows[-1]).all()


@pytest.mark.req("REQ-G2D-243")
def test_no_rows_give_no_rows(ctx: Context) -> None:
    built = rows_from_bulges(_points([]), _points([]), np.empty(0), ctx)
    assert built.rows.shape == (0, 7)
    assert built.status.shape == (0,)


@pytest.mark.req("REQ-G2D-244")
@pytest.mark.parametrize("sweep", [math.pi / 2, -math.pi / 2, math.pi, math.radians(359.0), 1e-3])
def test_sweeps_keep_the_given_sweep(ctx: Context, sweep: float) -> None:
    p0, p1 = (1.0, 2.0), (4.0, 6.0)
    built = rows_from_sweeps(_points([p0]), _points([p1]), np.array([sweep]), ctx)
    assert built.status[0] == RowStatus.OK
    row = built.rows[0]
    assert same_bits(row[:4], np.array([*p0, *p1]))
    assert row[6] == sweep  # the sweep as given, not 4·atan(tan(φ/4))
    via_bulge = arc_from_bulge(p0, p1, math.tan(sweep / 4), ctx).value
    assert isinstance(via_bulge, Arc)
    assert same_bits(row[4:6], np.array(via_bulge.centre))  # on the bisector, as for a bulge
    assert make_arc(p0, p1, via_bulge.centre, sweep, ctx).ok


@pytest.mark.req("REQ-G2D-244")
def test_a_tiny_radius_gives_make_arcs_line(ctx: Context) -> None:
    p1 = (1.5 * ctx.tolerances.length_eps_mm, 0.0)  # sagitta 1.5·eps_len, r = 0.9375·eps_len
    sweep = 4 * math.atan(2.0)
    built = rows_from_sweeps(_points([(0.0, 0.0)]), _points([p1]), np.array([sweep]), ctx)
    assert built.status[0] == RowStatus.OK
    assert same_bits(built.rows[0], np.array([0.0, 0.0, *p1, math.nan, math.nan, 0.0]))


@pytest.mark.req("REQ-G2D-244")
def test_a_tiny_sweep_gives_a_line(ctx: Context) -> None:
    built = rows_from_sweeps(_points([(0.0, 0.0)]), _points([(1.0, 0.0)]), np.array([1e-9]), ctx)
    expected, _ = scalar_row(arc_from_bulge((0.0, 0.0), (1.0, 0.0), math.tan(1e-9 / 4), ctx))
    assert same_bits(built.rows[0], expected)
    assert built.rows[0][6] == 0.0


@pytest.mark.req("REQ-G2D-244")
@pytest.mark.parametrize("sweep", [0.0, -0.0, math.tau, -math.tau, 7.0, math.nan, math.inf])
def test_sweeps_outside_the_open_turn_are_invalid(ctx: Context, sweep: float) -> None:
    built = rows_from_sweeps(_points([(0.0, 0.0)]), _points([(1.0, 0.0)]), np.array([sweep]), ctx)
    assert built.status[0] == RowStatus.CURVE_INVALID
    assert np.isnan(built.rows[0]).all()


def _arc(start_deg: float, sweep_deg: float) -> Arc:
    # An arc of radius 2 about (1, -1), its ends computed from the angles.
    centre, radius = (1.0, -1.0), 2.0
    end = math.radians(start_deg + sweep_deg)
    p0 = (centre[0] + radius * math.cos(math.radians(start_deg)),
          centre[1] + radius * math.sin(math.radians(start_deg)))  # fmt: skip
    p1 = (centre[0] + radius * math.cos(end), centre[1] + radius * math.sin(end))
    if sweep_deg in (360.0, -360.0):
        p1 = p0
    return Arc(p0, p1, centre, math.radians(sweep_deg))


@pytest.mark.req("REQ-G2D-245")
def test_row_boxes_equal_bounding_box(ctx: Context) -> None:
    curves = [
        Line((3.0, -1.0), (-2.0, 4.0)),
        _arc(10.0, 70.0),  # inside one quadrant
        _arc(10.0, -70.0),
        _arc(45.0, 90.0),  # across the +y axis
        _arc(-45.0, -90.0),  # clockwise across the -y axis
        _arc(30.0, 180.0),  # across +y and -x
        _arc(0.0, 90.0),  # starting on an axis
        _arc(0.0, 360.0),  # a full circle
        _arc(90.0, -360.0),
        # Unchecked rows whose P1 lies four octants from P0, against a sweep beyond 3π/2 or below
        # π/2: _box.py lets the sweep decide (all axes, none).
        Arc((3.0, -1.0), (-1.0, -1.0), (1.0, -1.0), 5.0),
        Arc((3.0, -1.0), (-1.0, -1.0), (1.0, -1.0), -1.0),
    ]
    rows = np.array([curve_row(c) for c in curves])
    boxes = row_boxes(rows, ctx)
    assert boxes.shape == (len(curves), 4)
    for i, curve in enumerate(curves):
        box = bounding_box(curve, ctx)
        assert tuple(boxes[i]) == (box.x_min_mm, box.y_min_mm, box.x_max_mm, box.y_max_mm), i


@pytest.mark.req("REQ-G2D-247")
def test_wrong_shapes_raise(ctx: Context) -> None:
    two = _points([(0.0, 0.0), (1.0, 0.0)])
    with pytest.raises(ValueError, match="p1"):
        rows_from_bulges(two, _points([(1.0, 1.0)]), np.zeros(2), ctx)
    with pytest.raises(ValueError, match="bulges"):
        rows_from_bulges(two, two, np.zeros(3), ctx)
    with pytest.raises(ValueError, match="sweeps_rad"):
        rows_from_sweeps(two, two, np.zeros((2, 1)), ctx)
    with pytest.raises(ValueError, match="bulges"):
        rows_from_bulges(two, two, [0.0, 0.0], ctx)  # pyright: ignore[reportArgumentType] (the error under test)
    with pytest.raises(ValueError, match="rows"):
        row_boxes(np.zeros((2, 6)), ctx)
    wrong_dtype = np.zeros((2, 2), dtype=np.int64)
    with pytest.raises(ValueError, match="p0"):
        rows_from_bulges(wrong_dtype, two, np.zeros(2), ctx)  # pyright: ignore[reportArgumentType] (the error under test)
