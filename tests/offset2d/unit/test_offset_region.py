# SPDX-License-Identifier: Apache-2.0
"""Unit tests of `offset_region` (plan 0005, step 4): research 02's tests 6, 7, 8, 11, 14 and 18,
the clean-up before the kernel, the diagnostics and refusals, and the orientation guard: test 21
and an inner loop that wins Clipper2's tie for the extreme point (DEC-OFF-011)."""

import json
import logging
import math

import numpy as np
import pytest

from geometry2d_checks import codes, reversed_loop
from offset2d_oracles import (
    DistanceBand,
    distance_to_curves,
    in_offset,
    offset_band_mm,
    polygon_rows,
    sample_outside_band,
    true_curve_band_mm,
)
from offset2d_strategies import circle, rounded_box, to_curve_rows
from splintercam import _kernels
from splintercam.foundation import CANCELLED, Context, Severity
from splintercam.geometry2d import (
    CurveRows,
    PointLocation,
    PolygonRegion,
    RegionKind,
    build_region,
    flatten_loops,
    loop_tree,
    point_in_region,
)
from splintercam.offset2d import EdgeClass, SourceClasses, offset_region

AIR, MATERIAL = RegionKind.AIR, RegionKind.MATERIAL
NAN = math.nan


def classes(loops: CurveRows, kind: EdgeClass = EdgeClass.MATERIAL) -> SourceClasses:
    ids = np.unique(loops.ids)
    return SourceClasses(ids, np.full(ids.size, int(kind), dtype=np.int8))


def offset(loops: CurveRows, kind: RegionKind, t_mm: float, ctx: Context) -> PolygonRegion:
    result = offset_region(loops, kind, t_mm, classes(loops), ctx)
    assert result.value is not None, result.diagnostics
    return result.value


def areas(region: PolygonRegion) -> list[float]:
    ends = [*region.loop_starts.tolist()[1:], region.points.shape[0]]
    out: list[float] = []
    for a, b in zip(region.loop_starts.tolist(), ends, strict=True):
        x, y = region.points[a:b, 0], region.points[a:b, 1]
        out.append(0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)))
    return out


def box_loop(x0: float, y0: float, x1: float, y1: float) -> list[list[float]]:
    return rounded_box(x0, y0, x1, y1, 0.0)


def assert_in_band(region: PolygonRegion, loops: CurveRows, t_mm: float, ctx: Context) -> None:
    # Lines only, so the flattened input is the true one: every vertex in [t, t + a + 6u].
    d = distance_to_curves(region.points, loops)
    assert d.min() >= t_mm
    assert d.max() <= t_mm + offset_band_mm(ctx.tolerances)


@pytest.mark.req("REQ-OFF-020", "REQ-OFF-025")
def test_the_rectangle_shrinks_by_10_within_the_band(ctx: Context) -> None:
    # Research 02, test 7.
    loops = to_curve_rows([box_loop(0.0, 0.0, 100.0, 60.0)], ctx)
    region = offset(loops, AIR, 10.0, ctx)
    assert region.loop_starts.tolist() == [0]
    assert_in_band(region, loops, 10.0, ctx)
    assert areas(region)[0] == pytest.approx(80.0 * 40.0, abs=1.0)


@pytest.mark.req("REQ-OFF-039")
@pytest.mark.parametrize("t_mm", [30.0, 31.0])
def test_the_rectangle_shrunk_by_its_half_width_is_empty(t_mm: float, ctx: Context) -> None:
    # Research 02, test 7: at 30 the offset area is a segment, which an area offset returns as
    # nothing (Held, limit 4).
    loops = to_curve_rows([box_loop(0.0, 0.0, 100.0, 60.0)], ctx)
    result = offset_region(loops, AIR, t_mm, classes(loops), ctx)
    assert result.value is not None
    assert result.value.loop_starts.size == 0
    assert codes(result) == ["OFFSET_EMPTY"]
    assert result.diagnostics[0].severity is Severity.INFO


@pytest.mark.req("REQ-OFF-020", "REQ-OFF-025", "REQ-OFF-039")
def test_the_annulus_shrinks_to_its_ring_and_then_to_nothing(ctx: Context) -> None:
    # Research 02, test 6: border radius 20, island radius 10, same centre.
    loops = to_curve_rows(
        [circle(0.0, 0.0, 20.0, 0.0, 1), reversed_loop(circle(0.0, 0.0, 10.0, 0.0, 1))], ctx
    )
    region = offset(loops, AIR, 3.0, ctx)
    assert len(region.loop_starts) == 2
    radii = np.hypot(region.points[:, 0], region.points[:, 1])
    band = offset_band_mm(ctx.tolerances) + ctx.tolerances.flatten_tol_mm
    assert (radii >= 13.0 - band).all()
    assert (radii <= 17.0 + band).all()
    assert sorted(np.sign(areas(region)).tolist()) == [-1.0, 1.0]  # a ring: outer and hole
    empty = offset_region(loops, AIR, 8.0, classes(loops), ctx)
    assert codes(empty) == ["OFFSET_EMPTY"]


@pytest.mark.req("REQ-OFF-020", "REQ-OFF-026")
@pytest.mark.parametrize(("t_mm", "pieces"), [(7.9, 1), (8.1, 2)])
def test_the_strait_splits_between_its_half_widths(t_mm: float, pieces: int, ctx: Context) -> None:
    # Research 02, test 8 (Held test 4): notches with apexes (50, 12) and (50, 28) leave a strait
    # of width 8 about (50, 20).
    notched = [
        (0.0, 0.0), (44.0, 0.0), (50.0, 12.0), (56.0, 0.0), (100.0, 0.0),
        (100.0, 40.0), (56.0, 40.0), (50.0, 28.0), (44.0, 40.0), (0.0, 40.0),
    ]  # fmt: skip
    rows = [[*p, *notched[(k + 1) % len(notched)], NAN, NAN, 0.0] for k, p in enumerate(notched)]
    loops = to_curve_rows([rows], ctx)
    assert len(offset(loops, AIR, t_mm, ctx).loop_starts) == pieces


@pytest.mark.req("REQ-OFF-020", "REQ-OFF-025")
def test_a_material_rectangle_grows_with_round_corners(ctx: Context) -> None:
    # Research 02, test 14's shape: 60 x 40 grown by 5 is the rounded rectangle.
    loops = to_curve_rows([box_loop(0.0, 0.0, 60.0, 40.0)], ctx)
    region = offset(loops, MATERIAL, 5.0, ctx)
    assert region.loop_starts.tolist() == [0]
    assert_in_band(region, loops, 5.0, ctx)
    exact = 60.0 * 40.0 + 2.0 * (60.0 + 40.0) * 5.0 + math.pi * 25.0
    assert areas(region)[0] == pytest.approx(exact, rel=1e-4)


@pytest.mark.req("REQ-OFF-024")
@pytest.mark.parametrize("kind", [AIR, MATERIAL])
def test_a_clearance_of_0_is_the_region_of_build_region(kind: RegionKind, ctx: Context) -> None:
    # Research 02, test 11.
    loops = to_curve_rows(
        [rounded_box(0.0, 0.0, 60.0, 40.0, 5.0), reversed_loop(circle(30.0, 20.0, 6.0, 0.3, 2))],
        ctx,
    )
    result = offset_region(loops, kind, 0.0, classes(loops), ctx)
    expected = build_region(loops, kind, ctx)
    assert result.value is not None
    assert expected.value is not None
    assert result.value.points.tobytes() == expected.value.region.points.tobytes()
    assert result.value.source_ids.tobytes() == expected.value.region.source_ids.tobytes()
    assert result.diagnostics == expected.diagnostics


@pytest.mark.req("REQ-OFF-018")
@pytest.mark.parametrize(("width_mm", "t_mm"), [(6712.0, 1.0), (6700.0, 10.0)])
def test_a_region_spanning_the_limit_is_refused(width_mm: float, t_mm: float, ctx: Context) -> None:
    # Research 02, test 18: 2^26 grid units of 0.0001 mm are about 6711 mm; growing adds 2t.
    loops = to_curve_rows([box_loop(0.0, 0.0, width_mm, 10.0)], ctx)
    result = offset_region(loops, MATERIAL, t_mm, classes(loops), ctx)
    assert result.value is None
    assert codes(result) == ["REGION_TOO_LARGE"]


@pytest.mark.req("REQ-OFF-018")
def test_a_region_just_inside_the_limit_is_offset(ctx: Context) -> None:
    loops = to_curve_rows([box_loop(0.0, 0.0, 6690.0, 10.0)], ctx)
    assert offset_region(loops, MATERIAL, 10.0, classes(loops), ctx).ok


@pytest.mark.req("REQ-OFF-043")
def test_vertices_closer_than_eps_len_are_cleaned_before_the_offset(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    near = [(0.0, 0.0), (10.0, 0.0), (10.0 + 0.5 * eps, 0.5 * eps), (10.0, 10.0), (0.0, 10.0)]
    regions: list[PolygonRegion] = []
    for points in (square, near):
        rows = [[*p, *points[(k + 1) % len(points)], NAN, NAN, 0.0] for k, p in enumerate(points)]
        regions.append(offset(to_curve_rows([rows], ctx), AIR, 2.0, ctx))
    assert regions[0].points.tobytes() == regions[1].points.tobytes()


@pytest.mark.req("REQ-OFF-040")
def test_crossing_loops_give_no_region_and_geometry2d_s_diagnostics(ctx: Context) -> None:
    loops = to_curve_rows([box_loop(0.0, 0.0, 10.0, 10.0), box_loop(5.0, 5.0, 15.0, 15.0)], ctx)
    result = offset_region(loops, AIR, 1.0, classes(loops), ctx)
    assert result.value is None
    assert codes(result) == ["LOOPS_CROSS"]


@pytest.mark.req("REQ-OFF-041")
def test_a_cancelled_context_gives_no_region(ctx: Context) -> None:
    loops = to_curve_rows([box_loop(0.0, 0.0, 10.0, 10.0)], ctx)
    ctx.cancel.cancel()
    result = offset_region(loops, AIR, 1.0, classes(loops), ctx)
    assert result.value is None
    assert result.diagnostics == (CANCELLED,)


@pytest.mark.req("REQ-OFF-013")
@pytest.mark.parametrize("t_mm", [-1.0, math.nan, math.inf])
def test_a_bad_clearance_is_refused(t_mm: float, ctx: Context) -> None:
    loops = to_curve_rows([box_loop(0.0, 0.0, 10.0, 10.0)], ctx)
    with pytest.raises(ValueError, match="clearance"):
        offset_region(loops, AIR, t_mm, classes(loops), ctx)


@pytest.mark.req("REQ-OFF-013")
def test_a_source_id_without_a_class_is_refused(ctx: Context) -> None:
    loops = to_curve_rows([box_loop(0.0, 0.0, 10.0, 10.0)], ctx)
    partial = SourceClasses(loops.ids[:2].copy(), np.zeros(2, dtype=np.int8))
    with pytest.raises(ValueError, match="class"):
        offset_region(loops, AIR, 1.0, partial, ctx)


@pytest.mark.req("REQ-OFF-014", "REQ-OFF-042")
def test_a_join_needing_more_steps_than_the_limit_fails(ctx: Context) -> None:
    # The kernel takes the step limit as a plain value; a lower one forces the failure.
    square = np.array([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])
    u = ctx.tolerances.grid_unit_mm
    a = ctx.tolerances.arc_tol_mm
    room = 64
    out = (np.empty((room, 2)), np.empty(room, np.int64), np.empty(room, np.int64))
    status = _kernels.offset2d.offset_loops(
        square, np.array([0], np.int64), np.arange(4, dtype=np.int64),
        (5.0 + a + 3 * u, a, 3.0, 6.0), (u, 2.0**26, 8.0), *out, np.empty(room, np.uint8),
    )[0]  # fmt: skip
    assert status == 2  # failed: 8 steps per turn are fewer than a round join needs


@pytest.mark.req("REQ-OFF-021")
def test_the_loops_reach_the_kernel_normalised(ctx: Context) -> None:
    wall, island = circle(0.0, 0.0, 20.0, 0.3, 2), reversed_loop(circle(0.0, 5.0, 4.0, 0.3, 2))
    drawn = offset(to_curve_rows([wall, island], ctx), AIR, 2.0, ctx)
    turned = offset(to_curve_rows([reversed_loop(island), reversed_loop(wall)], ctx), AIR, 2.0, ctx)
    assert drawn.points.tobytes() == turned.points.tobytes()


def assert_matches_oracle(
    loops: CurveRows, kind: RegionKind, t_mm: float, region: PolygonRegion, ctx: Context
) -> None:
    """Research 02, test 9's oracle at 10^4 points outside the band of the true curves."""
    rows = loops.rows
    corners = np.concatenate([rows[:, 0:2], rows[:, 2:4]])
    low, high = corners.min(axis=0) - t_mm - 2.0, corners.max(axis=0) + t_mm + 2.0
    box = (float(low[0]), float(low[1]), float(high[0]), float(high[1]))
    band = DistanceBand(t_mm, true_curve_band_mm(ctx.tolerances))
    points = sample_outside_band(loops, band, box, 10_000, 7)
    located = point_in_region(points, polygon_rows(region.points, region.loop_starts), ctx)
    assert np.array_equal(located == PointLocation.IN, in_offset(points, loops, kind, t_mm))


def assert_no_guard_left(
    loops: CurveRows, kind: RegionKind, region: PolygonRegion, t_mm: float, ctx: Context
) -> None:
    """No point lies above the flattened input's top plus the band's top (REQ-OFF-025), so the
    guard triangle is gone: grown, its lowest point lies above that line (REQ-OFF-023)."""
    tree = loop_tree(loops, ctx).value
    assert tree is not None
    top = float(flatten_loops(tree, kind, ctx).region.points[:, 1].max())
    if region.points.shape[0] > 0:
        assert region.points[:, 1].max() <= top + t_mm + offset_band_mm(ctx.tolerances)


@pytest.mark.req("REQ-OFF-023", "REQ-OFF-020")
def test_an_island_holding_the_extreme_point_is_offset_through_the_guard(ctx: Context) -> None:
    # Research 02, test 21: an island of radius 5 tangent inside a wall of radius 20 at its top.
    # In a region of air the island's flattening reaches above the wall's, so Clipper2 would take
    # the island for the outer loop and invert the offset (measured: an empty result); the guard
    # triangle above the input takes the extreme point instead (DEC-OFF-008, DEC-OFF-011).
    loops = to_curve_rows(
        [circle(0.0, 0.0, 20.0, 0.3, 1), reversed_loop(circle(0.0, 15.0, 5.0, 0.3, 1))], ctx
    )
    region = offset(loops, AIR, 2.0, ctx)
    assert region.loop_starts.size >= 1
    assert_matches_oracle(loops, AIR, 2.0, region, ctx)
    assert_no_guard_left(loops, AIR, region, 2.0, ctx)


@pytest.mark.req("REQ-OFF-023", "REQ-OFF-020")
@pytest.mark.parametrize("kind", [AIR, MATERIAL])
@pytest.mark.parametrize("t_mm", [0.5, 3.0, 9.0])
def test_a_loop_listed_first_at_the_wall_s_top_left_corner_goes_through_the_guard(
    kind: RegionKind, t_mm: float, ctx: Context
) -> None:
    # The loop tree keeps the input order, so an inner loop listed before its wall and touching
    # the wall's top-left corner wins Clipper2's tie for the extreme point (spec review,
    # 2026-10-09): the guard must handle it for both kinds, shrinking and growing.
    inner = reversed_loop(rounded_box(0.0, 30.0, 20.0, 40.0, 0.0))  # its corner at (0, 40)
    loops = to_curve_rows([inner, box_loop(0.0, 0.0, 60.0, 40.0)], ctx)
    region = offset(loops, kind, t_mm, ctx)
    assert_matches_oracle(loops, kind, t_mm, region, ctx)
    assert_no_guard_left(loops, kind, region, t_mm, ctx)


@pytest.mark.req("REQ-OFF-018", "REQ-OFF-023")
def test_the_span_check_counts_the_guard(ctx: Context) -> None:
    # A tall part grown by 10: 6680 + 2·10 mm fits the 6711 mm limit, but with a hole holding the
    # extreme point the guard above it adds about 3·|δ| more, and the call is refused.
    plain = to_curve_rows([box_loop(0.0, 0.0, 10.0, 6680.0)], ctx)
    assert offset_region(plain, MATERIAL, 10.0, classes(plain), ctx).ok
    hole = reversed_loop(rounded_box(0.0, 6670.0, 5.0, 6680.0, 0.0))
    guarded = to_curve_rows([hole, box_loop(0.0, 0.0, 10.0, 6680.0)], ctx)
    result = offset_region(guarded, MATERIAL, 10.0, classes(guarded), ctx)
    assert result.value is None
    assert codes(result) == ["REGION_TOO_LARGE"]
    # Grown by 5 the guard still fits: 6680 + 2·5 for the offset, about 3·5 + 1 for the guard.
    assert offset_region(guarded, MATERIAL, 5.0, classes(guarded), ctx).ok


@pytest.mark.req("REQ-OFF-020")
def test_the_same_shape_as_material_grows_correctly(ctx: Context) -> None:
    # As material the wall's flattening lies outside the true circle and holds the extreme point,
    # so the orientation guess is right: radius 22 outside, the island's hole shrunk to radius 3.
    loops = to_curve_rows(
        [circle(0.0, 0.0, 20.0, 0.3, 1), reversed_loop(circle(0.0, 15.0, 5.0, 0.3, 1))], ctx
    )
    region = offset(loops, MATERIAL, 2.0, ctx)
    assert sorted(round(a) for a in areas(region)) == [
        round(-math.pi * 9.0),
        round(math.pi * 484.0),
    ]


@pytest.mark.req("REQ-OFF-034")
def test_every_vertex_carries_an_input_id(ctx: Context) -> None:
    loops = to_curve_rows([rounded_box(0.0, 0.0, 60.0, 40.0, 5.0)], ctx)
    region = offset(loops, AIR, 3.0, ctx)
    assert set(region.source_ids.tolist()) <= set(loops.ids.tolist())
    assert polygon_rows(region.points, region.loop_starts).rows.shape[0] == region.points.shape[0]


@pytest.mark.req("REQ-OFF-039", "REQ-OFF-040")
def test_a_region_whose_loops_are_all_dropped_is_empty(ctx: Context) -> None:
    # A sliver the loop tree drops (LOOP_DEGENERATE, a warning) leaves nothing to offset.
    sliver = [[0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0], [10.0, 0.0, 0.0, 1e-9, NAN, NAN, 0.0],
              [0.0, 1e-9, 0.0, 0.0, NAN, NAN, 0.0]]  # fmt: skip
    loops = to_curve_rows([sliver], ctx)
    result = offset_region(loops, AIR, 1.0, classes(loops), ctx)
    assert result.value is not None
    assert result.value.loop_starts.size == 0
    assert codes(result) == ["LOOP_DEGENERATE", "OFFSET_EMPTY"]


@pytest.mark.req("REQ-OFF-013")
def test_a_kind_that_is_not_a_region_kind_is_refused(ctx: Context) -> None:
    loops = to_curve_rows([box_loop(0.0, 0.0, 10.0, 10.0)], ctx)
    with pytest.raises(ValueError, match="RegionKind"):
        offset_region(loops, "AIR", 1.0, classes(loops), ctx)  # pyright: ignore[reportArgumentType]


@pytest.mark.req("REQ-OFF-014")
def test_a_failed_offset_logs_its_kernel_input_for_replay(
    ctx: Context, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # With the guard, no input of offset_region is known to fail, so the kernel is replaced by one
    # that reports a failure (status 2); everything around it runs as usual.
    def failing(*_: object) -> tuple[int, int, int]:
        return (2, 0, 0)

    monkeypatch.setattr(_kernels.offset2d, "offset_loops", failing)
    loops = to_curve_rows([box_loop(0.0, 0.0, 10.0, 10.0)], ctx)
    with caplog.at_level(logging.ERROR, logger=ctx.logger.name):
        result = offset_region(loops, AIR, 2.0, classes(loops), ctx)
    assert codes(result) == ["OFFSET_FAILED"]
    dump = json.loads(caplog.records[-1].getMessage().split("replay: ", 1)[1])
    keys = {"points", "loop_starts", "source_ids", "delta_mm", "arc_tol_mm", "grid_unit_mm"}
    assert keys <= set(dump)
    assert dump["delta_mm"] < 0.0  # air shrinks
