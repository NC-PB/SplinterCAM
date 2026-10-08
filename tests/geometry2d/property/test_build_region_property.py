# SPDX-License-Identifier: Apache-2.0
"""Differential tests of the machining region against the loop tree (research 01, test 7):
nested rounded boxes of lines and quarter arcs, in any order and orientation."""

import math
import random

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows, RegionKind, build_region, curve_rows, point_in_region
from splintercam.geometry2d._grid import FillRule, region_with_fill_rule
from splintercam.geometry2d._loops import flatten_loops
from splintercam.geometry2d._tree import loop_tree

Rounded = tuple[float, float, float, float, float]  # x0, y0, x1, y1, corner radius
NAN = math.nan


@st.composite
def _nested(draw: st.DrawFn, min_gap: float) -> list[Rounded]:
    """Up to three columns of rounded boxes, each nested up to four deep. Each inner box is its
    parent offset inwards by a gap of at least `min_gap` (radius max(rho - gap, 0)), so the true
    boundaries are exactly that gap apart."""
    shapes: list[Rounded] = []
    for column in range(draw(st.integers(1, 3))):
        x0, y0, x1, y1 = 40.0 * column, 0.0, 40.0 * column + 30.0, 30.0
        rho = draw(st.sampled_from([0.0, 1.0, 4.0, 7.5]))
        for _ in range(draw(st.integers(1, 4))):
            shapes.append((x0, y0, x1, y1, rho))
            gap = draw(st.floats(min_gap, 3.0))
            x0, y0, x1, y1, rho = x0 + gap, y0 + gap, x1 - gap, y1 - gap, max(rho - gap, 0.0)
    return shapes


def _rows(shape: Rounded) -> list[list[float]]:
    """The CCW loop of a rounded box: a line per side, a quarter arc per corner when rho > 0."""
    x0, y0, x1, y1, r = shape
    corners = [
        (x1 - r, y0 + r, -math.pi / 2),
        (x1 - r, y1 - r, 0.0),
        (x0 + r, y1 - r, math.pi / 2),
        (x0 + r, y0 + r, math.pi),
    ]
    rows: list[list[float]] = []
    for k, (cx, cy, a) in enumerate(corners):
        start = (cx + r * math.cos(a), cy + r * math.sin(a))
        end = (cx + r * math.cos(a + math.pi / 2), cy + r * math.sin(a + math.pi / 2))
        if r > 0.0:
            rows.append([*start, *end, cx, cy, math.pi / 2])
        nx, ny, na = corners[(k + 1) % 4]
        rows.append([*end, nx + r * math.cos(na), ny + r * math.sin(na), NAN, NAN, 0.0])
    return rows


def _loops(shapes: list[Rounded], order: list[int], flips: list[bool], ctx: Context) -> CurveRows:
    loops: list[list[list[float]]] = []
    for k in order:
        rows = _rows(shapes[k])
        loops.append(
            [[x1, y1, x0, y0, cx, cy, -s] for x0, y0, x1, y1, cx, cy, s in rows[::-1]]
            if flips[k]
            else rows
        )
    rows = np.array([row for one in loops for row in one], dtype=np.float64)
    starts = np.cumsum([0] + [len(one) for one in loops[:-1]], dtype=np.int64)
    built = curve_rows(rows, np.arange(rows.shape[0], dtype=np.int64), starts, ctx)
    assert built.value is not None, built.diagnostics
    return built.value


def _distance(q: NDArray[np.float64], shapes: list[Rounded]) -> NDArray[np.float64]:
    """Each point's distance to the nearest true boundary (the rounded box's distance field)."""
    nearest = np.full(q.shape[0], np.inf)
    for x0, y0, x1, y1, r in shapes:
        centre = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
        d = np.abs(q - centre) - (np.array([(x1 - x0) / 2, (y1 - y0) / 2]) - r)
        outside = np.sqrt((np.maximum(d, 0.0) ** 2).sum(axis=1))
        nearest = np.minimum(nearest, np.abs(outside + np.minimum(d.max(axis=1), 0.0) - r))
    return nearest


def _rows_of(points: NDArray[np.float64], starts: NDArray[np.int64]) -> CurveRows:
    ends = np.append(starts[1:], points.shape[0])
    rows = [
        [*p, *q, NAN, NAN, 0.0]
        for a, b in zip(starts.tolist(), ends.tolist(), strict=True)
        for p, q in zip(
            points[a:b].tolist(), np.roll(points[a:b], -1, axis=0).tolist(), strict=True
        )
    ]
    return CurveRows(np.array(rows).reshape(-1, 7), np.arange(len(rows), dtype=np.int64), starts)


_CASE = {
    "seed": st.integers(0, 2**32 - 1),
    "flips": st.lists(st.booleans(), min_size=12, max_size=12),
    "kind": st.sampled_from(list(RegionKind)),
}


def _margin(ctx: Context) -> float:
    return ctx.tolerances.flatten_tol_mm + 3.0 * ctx.tolerances.grid_unit_mm


def _queries(seed: int, shapes: list[Rounded], margin: float) -> NDArray[np.float64]:
    q = np.random.default_rng(seed).uniform((-5.0, -5.0), (125.0, 35.0), size=(400, 2))
    return q[_distance(q, shapes) > margin]


@pytest.mark.req("REQ-G2D-176", "REQ-G2D-178")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(shapes=_nested(0.01), **_CASE)
def test_the_region_classifies_points_as_the_tree_does(
    ctx: Context, shapes: list[Rounded], seed: int, flips: list[bool], kind: RegionKind
) -> None:
    order = list(range(len(shapes)))
    random.Random(seed).shuffle(order)
    loops = _loops(shapes, order, flips, ctx)
    tree = loop_tree(loops, ctx).value
    built = build_region(loops, kind, ctx)
    assert tree is not None
    assert built.ok, built.diagnostics
    assert built.value is not None
    region = built.value.region
    q = _queries(seed, shapes, _margin(ctx))
    expected = point_in_region(q, tree.loops, ctx)
    assert (point_in_region(q, _rows_of(region.points, region.loop_starts), ctx) == expected).all()


@pytest.mark.req("REQ-G2D-177", "REQ-G2D-179")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(shapes=_nested(0.05), **_CASE)
def test_apart_loops_keep_their_depth_and_every_fill_rule(
    ctx: Context, shapes: list[Rounded], seed: int, flips: list[bool], kind: RegionKind
) -> None:
    assert 2.0 * ctx.tolerances.flatten_tol_mm + 6.0 * ctx.tolerances.grid_unit_mm < 0.05
    order = list(range(len(shapes)))
    random.Random(seed).shuffle(order)
    tree = loop_tree(_loops(shapes, order, flips, ctx), ctx).value
    assert tree is not None
    flat = flatten_loops(tree, kind, ctx).region
    q = _queries(seed, shapes, _margin(ctx))
    inside: list[NDArray[np.int8]] = []
    for rule in FillRule:
        joined = region_with_fill_rule(flat, rule, ctx).value
        assert joined is not None
        assert joined.loop_starts.size == len(shapes)
        inside.append(point_in_region(q, _rows_of(joined.points, joined.loop_starts), ctx))
        # Each region loop's orientation is the parity of the tree loop it came from (REQ-G2D-179).
        ends = np.append(joined.loop_starts[1:], joined.points.shape[0])
        for a, b in zip(joined.loop_starts.tolist(), ends.tolist(), strict=True):
            p = joined.points[a:b]
            area = float((p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]).sum())
            source = int(np.bincount(joined.source_ids[a:b]).argmax())
            row = int(np.flatnonzero(tree.loops.ids == source)[0])
            depth = int(tree.depth[np.searchsorted(tree.loops.row_starts, row, side="right") - 1])
            assert (area > 0) == (depth % 2 == 0)
    assert np.array_equal(inside[0], inside[1])
    assert np.array_equal(inside[1], inside[2])
