# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the loop tree's first rules: cleanup, the area tests and duplicates (research 01,
Loop tree, rules 1 to 3; tests 7, 12 and 19)."""

import dataclasses
import math

import numpy as np
import pytest

from geometry2d_checks import codes
from splintercam.foundation import Context, ToleranceSet
from splintercam.geometry2d import CurveRows, curve_rows
from splintercam.geometry2d._screen import screen_loops

NAN = math.nan
Points = list[tuple[float, float]]


def _rows(points: Points) -> list[list[float]]:
    return [[*p, *q, NAN, NAN, 0.0] for p, q in zip(points, points[1:] + points[:1], strict=True)]


def _loops(polygons: list[Points], ctx: Context) -> CurveRows:
    rows = np.array([row for points in polygons for row in _rows(points)], dtype=np.float64)
    starts = np.cumsum([0] + [len(p) for p in polygons[:-1]], dtype=np.int64)
    built = curve_rows(rows, 100 + np.arange(rows.shape[0], dtype=np.int64), starts, ctx)
    assert built.value is not None, built.diagnostics
    return built.value


def _square(x0: float = 0.0, y0: float = 0.0, side: float = 10.0) -> Points:
    return [(x0, y0), (x0 + side, y0), (x0 + side, y0 + side), (x0, y0 + side)]


def _strip(width: float) -> Points:
    return [(0.0, 0.0), (10.0, 0.0), (10.0, width), (0.0, width)]


@pytest.mark.req("REQ-G2D-155")
def test_a_spike_is_cleaned_and_reported(ctx: Context) -> None:
    spike = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (10.0, 20.0), (10.0, 10.0), (0.0, 10.0)]
    result = screen_loops(_loops([spike], ctx), ctx)
    assert result.value is not None
    assert result.value.kept.tolist() == [0]
    assert codes(result) == ["CLEANUP_SPIKE"]
    assert result.diagnostics[0].location == "loop 0"
    polyline = result.value.polylines[0]
    assert (10.0, 20.0) not in [tuple(p) for p in polyline.tolist()]
    assert result.value.areas[0] == pytest.approx(100.0)


@pytest.mark.req("REQ-G2D-156")
def test_a_loop_failing_the_area_test_is_dropped(ctx: Context) -> None:
    result = screen_loops(_loops([_strip(1e-7)], ctx), ctx)  # research 01, test 19
    assert result.value is not None
    assert result.value.kept.size == 0
    assert codes(result) == ["LOOP_DEGENERATE"]
    assert result.diagnostics[0].location == "loop 0"


@pytest.mark.req("REQ-G2D-157")
@pytest.mark.parametrize(("width", "kept"), [(1e-5, False), (0.001, True)])
def test_a_loop_thinner_than_the_topology_tolerance_is_dropped(
    ctx: Context, width: float, kept: bool
) -> None:
    result = screen_loops(_loops([_strip(width)], ctx), ctx)  # research 01, test 19
    assert result.value is not None
    assert result.value.kept.tolist() == ([0] if kept else [])
    assert codes(result) == ([] if kept else ["LOOP_DEGENERATE"])


@pytest.mark.req("REQ-G2D-158", "REQ-G2D-159", "REQ-G2D-236")
def test_a_duplicate_loop_is_kept_once(ctx: Context) -> None:
    result = screen_loops(_loops([_square(), _square(20.0), _square()], ctx), ctx)
    assert result.value is not None
    assert result.value.kept.tolist() == [0, 1]
    assert codes(result) == ["LOOP_DUPLICATE"]
    assert result.diagnostics[0].location == "loops 0 and 2"


@pytest.mark.req("REQ-G2D-158")
@pytest.mark.parametrize(
    ("other", "duplicate"),
    [
        (_square()[::-1], True),  # reversed: orientation does not matter
        (_square(0.0001, 0.0001), True),  # within t_topo
        (_square(0.001, 0.0), False),
        ([(0, 0), (2, 0), (2, 5), (2.1, 5), (2.1, 0), (10, 0), (10, 10), (0, 10)], False),
    ],
)
def test_duplicates_are_within_t_topo_both_ways(
    ctx: Context, other: Points, duplicate: bool
) -> None:
    result = screen_loops(_loops([_square(), other], ctx), ctx)
    assert result.value is not None
    assert result.value.kept.tolist() == ([0] if duplicate else [0, 1])


@pytest.mark.req("REQ-G2D-159")
def test_the_first_duplicate_in_input_order_is_kept(ctx: Context) -> None:
    notched = [
        (0, 0),
        (2, 0),
        (2, 0.00005),
        (2.0001, 0.00005),
        (2.0001, 0),
        (10, 0),
        (10, 10),
        (0, 10),
    ]
    for order, expected in (([notched, _square()], 0), ([_square(), notched], 0)):
        result = screen_loops(_loops(order, ctx), ctx)  # a notch shallower than t_topo
        assert result.value is not None
        assert result.value.kept.tolist() == [expected]
        assert codes(result) == ["LOOP_DUPLICATE"]


@pytest.mark.req("REQ-G2D-154")
def test_the_screen_does_not_depend_on_the_operation_tolerance(ctx: Context) -> None:
    built = ToleranceSet.for_operation(0.05)
    assert built.value is not None
    rough = dataclasses.replace(ctx, tolerances=built.value)
    polygons = [_square(), _strip(1e-5), _square(), _square(20.0)]
    fine = screen_loops(_loops(polygons, ctx), ctx)
    other = screen_loops(_loops(polygons, rough), rough)
    assert fine.value is not None
    assert other.value is not None
    assert fine.value.kept.tolist() == other.value.kept.tolist() == [0, 3]
    assert codes(fine) == codes(other)


@pytest.mark.req("REQ-G2D-236")
def test_diagnostics_follow_input_loop_order(ctx: Context) -> None:
    spike = [(30.0, 0.0), (40.0, 0.0), (40.0, 10.0), (40.0, 20.0), (40.0, 10.0), (30.0, 10.0)]
    result = screen_loops(_loops([_strip(1e-7), _square(), spike, _square()], ctx), ctx)
    assert [(d.code, d.location) for d in result.diagnostics] == [
        ("LOOP_DEGENERATE", "loop 0"),
        ("CLEANUP_SPIKE", "loop 2"),
        ("LOOP_DUPLICATE", "loops 1 and 3"),
    ]
