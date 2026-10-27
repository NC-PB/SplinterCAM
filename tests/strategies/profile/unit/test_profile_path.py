# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the profile's path and record: the centre path in the band, clockwise, the start
and approach points, the passes, the header and the links (REQ-PRF-011 to 019, 022; research 22,
Method and tests 1, 2 and 5)."""

import math
from dataclasses import fields

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes, polygon
from offset2d_oracles import distance_to_curves, offset_band_mm, polygon_rows, true_curve_band_mm
from offset2d_strategies import bulge_row, circle, to_curve_rows
from profile_checks import (
    STOCK,
    cut_points,
    distance_to_box,
    make_context,
    pass_moves,
    point_segment_distance,
    rounded_rect_distances,
    signed_area,
    task,
    with_stock,
)
from splintercam.cl import ClHeader, ClMoves, ClOperation, MoveKind, Role, make_operation
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows, PolygonRegion, RegionKind, flatten_loops, loop_tree
from splintercam.model import StockBox
from splintercam.offset2d import EdgeClass, SourceClasses, offset_region
from splintercam.strategies.profile import plan_profile
from splintercam.strategies.profile._approach import approach_point
from splintercam.strategies.profile._passes import levels

LINE_IDS = (101, 103, 105, 107)  # rounded_box: an arc, then a line, per corner
H_C, H_R = 5.0, 3.0


def _op(ctx: Context, **changed: object) -> ClOperation:
    result = plan_profile(task(ctx, **changed), ctx)  # type: ignore[arg-type]
    assert result.value is not None, codes(result)
    return result.value


def _offset(contour: CurveRows, t_mm: float, ctx: Context) -> PolygonRegion:
    ids = np.unique(contour.ids)
    classes = SourceClasses(ids, np.full(ids.size, int(EdgeClass.MATERIAL), dtype=np.int8))
    region = offset_region(contour, RegionKind.MATERIAL, t_mm, classes, ctx).value
    assert region is not None
    return region


def _cut(op: ClOperation, index: int = 0) -> NDArray[np.float64]:
    # The closed CUT polyline of pass `index`, S first and last.
    rows = pass_moves(op)[index][1]
    return cut_points(op, rows[op.moves.role[rows] == Role.CUT])


def _approach(op: ClOperation) -> tuple[float, float]:
    return float(op.moves.end_mm[1, 0]), float(op.moves.end_mm[1, 1])  # the rapid over P


def _in_rect_band(op: ClOperation, t_mm: float, ctx: Context) -> None:
    # Every cut edge at least t from the true contour and within the band from it, exactly.
    for _, rows in pass_moves(op):
        smallest, largest = rounded_rect_distances(cut_points(op, rows[op.moves.role[rows]
                                                                     == Role.CUT]),
                                                   (5.0, 5.0, 95.0, 55.0), 5.0)  # fmt: skip
        assert smallest.min() >= t_mm - 1e-9
        assert largest.max() <= t_mm + true_curve_band_mm(ctx.tolerances)


@pytest.mark.req("REQ-PRF-011", "REQ-PRF-012")
def test_research_22_test_1_the_sides_are_edges_offset_by_5_and_the_fillets_in_the_band() -> None:
    ctx = make_context()
    op = _op(ctx)
    _in_rect_band(op, 5.0, ctx)
    cut = _cut(op)
    a, b = cut[:-1], cut[1:]
    width = true_curve_band_mm(ctx.tolerances)
    sides = [(1, -5.0), (1, 65.0), (0, -5.0), (0, 105.0)]  # (axis held, its value)
    for axis, value in sides:
        on = (np.abs(a[:, axis] - value) <= width) & (np.abs(b[:, axis] - value) <= width)
        on &= np.abs(b[:, 1 - axis] - a[:, 1 - axis]) > 1.0  # not a fillet's chord near its end
        length = np.abs(b[on, 1 - axis] - a[on, 1 - axis]).sum()
        assert on.sum() in (1, 2)  # 2 on the side S splits
        # The whole straight; past its ends the edge runs on along the flattened fillet, whose
        # points the band check above holds.
        assert length >= (90.0 if axis == 1 else 50.0) - 2 * width
    assert signed_area(cut) < 0.0  # clockwise


@pytest.mark.req("REQ-PRF-011")
def test_research_22_test_2_an_allowance_of_half_a_millimetre() -> None:
    ctx = make_context()
    op = _op(ctx, allowance_mm=0.5)
    _in_rect_band(op, 5.5, ctx)
    contour = task(ctx).contour
    tree = loop_tree(contour, ctx).value
    assert tree is not None
    flat = flatten_loops(tree, RegionKind.MATERIAL, ctx).region
    cut = _cut(op)
    probes = np.concatenate([cut, (cut[:-1] + cut[1:]) / 2.0])
    d = distance_to_curves(probes, polygon_rows(flat.points, flat.loop_starts))
    assert d.min() >= 5.5 - 1e-9
    assert d.max() <= 5.5 + offset_band_mm(ctx.tolerances)


@pytest.mark.req("REQ-PRF-003", "REQ-PRF-011")
def test_research_22_test_3_an_allowance_of_minus_4_9_gives_a_loop_at_0_1() -> None:
    ctx = make_context()
    _in_rect_band(_op(ctx, allowance_mm=-4.9), 5.0 - 4.9, ctx)


def _circle_task(ctx: Context) -> tuple[CurveRows, StockBox]:
    contour = to_curve_rows([circle(0.0, 0.0, 20.0, 0.0, 2)], ctx)
    return contour, StockBox((-30.0, -30.0, -20.0), (30.0, 30.0, 0.0))


@pytest.mark.req("REQ-PRF-011", "REQ-PRF-013", "REQ-PRF-014")
def test_research_22_test_5_a_circle_starts_at_its_smallest_vertex() -> None:
    ctx = make_context()
    contour, stock = _circle_task(ctx)
    op = _op(ctx, contour=contour, stock=stock)
    first = _offset(contour, 5.0, ctx).points[0]
    width = true_curve_band_mm(ctx.tolerances)
    for _, rows in pass_moves(op):
        cut = cut_points(op, rows[op.moves.role[rows] == Role.CUT])
        assert tuple(cut[0]) == tuple(first)
        assert tuple(cut[-1]) == tuple(first)
        near = point_segment_distance(np.zeros((1, 2)), cut[:-1], cut[1:])
        far = np.hypot(cut[:, 0], cut[:, 1])
        assert near.min() >= 25.0 - 1e-9
        assert far.max() <= 25.0 + width
    p = _approach(op)
    assert p[0] < first[0]
    assert abs(p[1] - first[1]) < 0.1 * (first[0] - p[0])  # about -x
    assert distance_to_box(p, stock) >= 6.0 - ctx.tolerances.length_eps_mm


@pytest.mark.req("REQ-PRF-012", "REQ-PRF-013")
def test_research_22_test_1_starts_at_the_middle_of_the_first_longest_side() -> None:
    ctx = make_context()
    region = _offset(task(ctx).contour, 5.0, ctx)
    p, ids = region.points, region.source_ids
    nxt = np.roll(p, -1, axis=0)
    length2 = np.where(np.isin(ids, LINE_IDS), np.sum((nxt - p) ** 2, axis=1), -1.0)
    k = int(np.argmax(length2))
    expected = (p[k] + nxt[k]) / 2.0
    cut = _cut(_op(ctx))
    assert tuple(cut[0]) == tuple(expected)
    assert abs(expected[0] - 50.0) < 1e-3
    assert min(abs(expected[1] + 5.0), abs(expected[1] - 65.0)) < 1e-3  # a long side
    assert tuple(cut[1]) == tuple(p[k])  # clockwise: on to the side's CCW start


@pytest.mark.req("REQ-PRF-013")
def test_a_tie_of_two_equal_sides_takes_the_first_in_offset2ds_order() -> None:
    ctx = make_context()
    part = polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)], ctx)
    stock = with_stock(STOCK, x1=105.0)
    region = _offset(part, 5.0, ctx)
    p, nxt = region.points, np.roll(region.points, -1, axis=0)
    length2 = np.sum((nxt - p) ** 2, axis=1)
    longest = np.flatnonzero(length2 == length2.max())
    assert longest.size == 2  # the two long sides, equal bit for bit
    cut = _cut(_op(ctx, contour=part, stock=stock))
    assert tuple(cut[0]) == tuple((p[longest[0]] + nxt[longest[0]]) / 2.0)


@pytest.mark.req("REQ-PRF-014")
def test_research_22_test_1_p_lies_6_mm_off_the_stock_along_the_axis() -> None:
    ctx = make_context()
    op = _op(ctx)
    s, p = _cut(op)[0], _approach(op)
    assert p[0] == s[0]  # n exactly along the axis
    assert distance_to_box(p, STOCK) >= 6.0 - ctx.tolerances.length_eps_mm
    assert distance_to_box(p, STOCK) <= 6.0 + ctx.tolerances.length_eps_mm


@pytest.mark.req("REQ-PRF-014")
def test_an_axis_normal_and_a_start_already_clear() -> None:
    assert approach_point((50.0, -5.0), (0.0, -1.0), STOCK, 6.0) == (50.0, -11.0)
    assert approach_point((-12.0, 30.0), (-1.0, 0.0), STOCK, 6.0) == (-12.0, 30.0)


@pytest.mark.req("REQ-PRF-014")
def test_p_off_a_box_corner_lies_on_the_corners_circle() -> None:
    root = math.sqrt(0.5)
    p = approach_point((106.0, 66.0), (root, root), STOCK, 6.0)
    assert abs(math.hypot(p[0] - 105.0, p[1] - 65.0) - 6.0) <= 1e-12
    assert abs((p[0] - 106.0) - (p[1] - 66.0)) <= 1e-12  # on the ray


def _u_part(ctx: Context) -> CurveRows:
    # A U opening up, outer sides bulging out (arcs), so the inner sides are the longest lines;
    # the inner right side's outward normal points across the U at the left arm.
    nan = math.nan
    rows = [
        [0.0, 0.0, 40.0, 0.0, nan, nan, 0.0],
        bulge_row((40.0, 0.0), (40.0, 100.0), 0.1),
        [40.0, 100.0, 30.0, 100.0, nan, nan, 0.0],
        [30.0, 100.0, 30.0, 10.0, nan, nan, 0.0],
        [30.0, 10.0, 10.0, 10.0, nan, nan, 0.0],
        [10.0, 10.0, 10.0, 100.0, nan, nan, 0.0],
        [10.0, 100.0, 0.0, 100.0, nan, nan, 0.0],
        bulge_row((0.0, 100.0), (0.0, 0.0), 0.1),
    ]
    return to_curve_rows([rows], ctx)


@pytest.mark.req("REQ-PRF-015")
def test_a_u_whose_inner_side_is_longest_starts_at_its_smallest_vertex() -> None:
    ctx = make_context()
    part = _u_part(ctx)
    stock = StockBox((-15.0, -10.0, -20.0), (55.0, 110.0, 0.0))
    op = _op(ctx, contour=part, stock=stock)
    first = _offset(part, 5.0, ctx).points[0]
    assert tuple(_cut(op)[0]) == tuple(first)
    assert _approach(op)[0] < first[0]


@pytest.mark.req("REQ-PRF-016")
@pytest.mark.parametrize(
    ("top", "bottom", "step", "expected"),
    [(0.0, -10.0, 4.0, [-10.0 / 3.0, -20.0 / 3.0, -10.0]), (0.1, -0.2, 0.1, None),
     (0.0, -4.0, 4.0, [-4.0]), (0.0, -5e-7, 4.0, [-5e-7])],
)  # fmt: skip
def test_equal_depth_passes(top: float, bottom: float, step: float,
                            expected: list[float] | None) -> None:  # fmt: skip
    eps = make_context().tolerances.length_eps_mm
    got = levels(top, bottom, step, eps)
    if expected is None:
        assert (0.1 - -0.2) / 0.1 > 3.0  # the quotient lands above 3
        assert len(got) == 3
        assert got[-1] == bottom
    else:
        assert got == pytest.approx(expected, abs=1e-12)
        assert got[-1] == bottom


@pytest.mark.req("REQ-PRF-016")
def test_research_22_test_1_cuts_three_passes() -> None:
    levels_cut = [z for z, _ in pass_moves(_op(make_context()))]
    assert levels_cut == pytest.approx([-10.0 / 3.0, -20.0 / 3.0, -10.0], abs=1e-12)
    assert levels_cut[-1] == -10.0


@pytest.mark.req("REQ-PRF-017")
def test_research_22_test_1s_pass_roles_and_feed_classes() -> None:
    op = _op(make_context())
    p = _approach(op)
    for _, rows in pass_moves(op):
        role, feed = op.moves.role[rows], op.moves.feed_class[rows]
        assert role[0] == Role.APPROACH
        assert feed[0] == 1  # plunge
        assert role[-1] == Role.RETRACT
        assert feed[-1] == 0  # cut
        assert (role[1:-1] == Role.CUT).all()
        assert (feed[1:-1] == 0).all()
        assert (op.moves.kind[rows] == MoveKind.LINE).all()
        assert tuple(op.moves.end_mm[rows[-1], 0:2]) == p


@pytest.mark.req("REQ-PRF-017")
def test_a_start_already_clear_gives_the_loop_alone() -> None:
    ctx = make_context()
    flush = with_stock(STOCK, x0=0.0, y0=0.0, x1=100.0, y1=60.0)
    op = _op(ctx, stock=flush, allowance_mm=2.0)
    for _, rows in pass_moves(op):
        assert (op.moves.role[rows] == Role.CUT).all()
        assert tuple(op.moves.end_mm[rows[-1], 0:2]) == _approach(op)


@pytest.mark.req("REQ-PRF-018")
def test_the_header_of_the_example_job() -> None:
    header = _op(make_context()).header
    assert header == ClHeader("PROFILE_1", (), 1, 1, 0.0, 8000.0, 0.01,
                              (("cut", 1200.0), ("plunge", 300.0)), H_C, H_R)  # fmt: skip


@pytest.mark.req("REQ-PRF-019")
def test_research_10_test_1_on_research_22_test_1s_record() -> None:
    ctx = make_context()
    op = _op(ctx)
    make_operation(op.header, op.moves, ctx)  # accepted again as it stands
    moves = op.moves
    rapid = moves.kind == MoveKind.RAPID
    moved = ~np.isnan(moves.end_mm[:, 0])
    starts = np.vstack([[np.nan, np.nan], moves.end_mm[:-1, 0:2]])
    across = rapid & moved & (moves.end_mm[:, 0:2] != starts).any(axis=1)
    assert (moves.end_mm[across, 2] == H_C).all()  # no RAPID in the plane below h_c
    low = moves.end_mm[:, 2] < H_R
    passes = pass_moves(op)
    in_pass = np.zeros(moves.kind.size, dtype=bool)
    for _, rows in passes:
        in_pass[rows] = True
    at_p = (moves.end_mm[:, 0:2] == _approach(op)).all(axis=1) & (moves.role == Role.APPROACH)
    assert not (low & ~in_pass & ~at_p).any()
    assert [z for z, _ in passes] == sorted((z for z, _ in passes), reverse=True)


@pytest.mark.req("REQ-PRF-022")
def test_research_22_test_1_twice_bit_for_bit() -> None:
    first, second = _op(make_context()), _op(make_context())
    assert first.header == second.header
    for field in fields(ClMoves):
        a, b = getattr(first.moves, field.name), getattr(second.moves, field.name)
        assert a.tobytes() == b.tobytes()
