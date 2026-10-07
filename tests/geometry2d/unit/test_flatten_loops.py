# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the side-correct flattening of regions (research 01, Flattening; tests 16, 20)."""

import dataclasses
import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import nested_tree, reversed_loop
from splintercam.foundation import Context, ToleranceSet
from splintercam.geometry2d import (
    AirSide,
    Arc,
    FlatRegion,
    RegionKind,
    arc_from_bulge,
    flatten,
    flatten_loops,
    polygon_region,
)

NAN = math.nan
# Research 01, test 16: the square [0, 10]² with its right side an outward semicircle (CCW arc,
# φ = +π about (10, 5)) and its top side an inward one (CW arc, φ = -π about (5, 10)). Normalised:
# the outer loop is CCW, the inside on the left.
OUTER = [
    [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0],
    [10.0, 0.0, 10.0, 10.0, 10.0, 5.0, math.pi],
    [10.0, 10.0, 0.0, 10.0, 5.0, 10.0, -math.pi],
    [0.0, 10.0, 0.0, 0.0, NAN, NAN, 0.0],
]
# An island in a pocket: a full circle of radius 1 about (4, 4), CW at depth 1.
ISLAND = [[5.0, 4.0, 5.0, 4.0, 4.0, 4.0, -math.tau]]
# Research 01, test 20's valid loops: a one-row full circle; a line closed by a CCW half circle.
CIRCLE = [5.0, 0.0, 5.0, 0.0, 0.0, 0.0, math.tau]
LINE_AND_ARC = [[0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0], [10.0, 0.0, 0.0, 0.0, 5.0, 0.0, math.pi]]


def _vertices_of(flat: FlatRegion, row_id: int) -> NDArray[np.float64]:
    return flat.region.points[flat.region.source_ids == row_id]


def _assert_no_repeats(points: NDArray[np.float64]) -> None:
    following = np.roll(points, -1, axis=0)
    assert not (points == following).all(axis=1).any()  # the closing edge included


def _rough(ctx: Context) -> Context:
    """`ctx` at tol = 0.05 mm, where t_flat = 0.002397 mm."""
    built = ToleranceSet.for_operation(0.05)
    assert built.value is not None
    return dataclasses.replace(ctx, tolerances=built.value)


def _arc(row: list[float]) -> Arc:
    return Arc((row[0], row[1]), (row[2], row[3]), (row[4], row[5]), row[6])


def _radii(points: NDArray[np.float64], centre: tuple[float, float]) -> NDArray[np.float64]:
    return np.hypot(points[:, 0] - centre[0], points[:, 1] - centre[1])


def _assert_side(flat: FlatRegion, row: list[float], row_id: int, outside: bool) -> None:
    """The arc's vertices beyond P0 lie outside its circle (circumscribed) or on it (inscribed)."""
    radius = math.hypot(row[0] - row[4], row[1] - row[5])
    radii = _radii(_vertices_of(flat, row_id)[1:], (row[4], row[5]))
    assert radii.size > 0
    if outside:
        assert radii.min() > radius
    else:
        assert np.abs(radii - radius).max() <= 4 * math.ulp(radius)  # REQ-G2D-110


@pytest.mark.req("REQ-G2D-115", "REQ-G2D-127")
def test_material_region_of_research_test_16(ctx: Context) -> None:
    flat = flatten_loops(nested_tree([OUTER], ctx), RegionKind.MATERIAL, ctx)
    _assert_side(flat, OUTER[1], 101, outside=True)  # CCW arc: circumscribed, into air
    _assert_side(flat, OUTER[2], 102, outside=False)  # CW arc: inscribed, into air
    assert flat.extra_clearance_mm == 0.0
    t_flat = ctx.tolerances.flatten_tol_mm
    # Material lies left of a normalised loop, so air lies right of every arc.
    for row, row_id in ((OUTER[1], 101), (OUTER[2], 102)):
        alone = flatten(_arc(row), t_flat, AirSide.RIGHT, ctx)
        np.testing.assert_array_equal(_vertices_of(flat, row_id), alone[:-1])  # bit for bit


@pytest.mark.req("REQ-G2D-116")
def test_the_same_arcs_in_a_pocket_flip(ctx: Context) -> None:
    flat = flatten_loops(nested_tree([OUTER], ctx), RegionKind.AIR, ctx)
    _assert_side(flat, OUTER[1], 101, outside=False)
    _assert_side(flat, OUTER[2], 102, outside=True)


@pytest.mark.req("REQ-G2D-116")
def test_an_island_in_a_pocket_is_flattened_into_air(ctx: Context) -> None:
    flat = flatten_loops(nested_tree([OUTER, ISLAND], ctx), RegionKind.AIR, ctx)
    _assert_side(flat, ISLAND[0], 104, outside=True)  # air lies outside the island
    assert flat.region.loop_starts.size == 2


@pytest.mark.req("REQ-G2D-127")
def test_step_counts_follow_t_flat(ctx: Context) -> None:
    t_flat = ctx.tolerances.flatten_tol_mm
    assert t_flat == pytest.approx(0.000397)  # tol = 0.01 mm (research 01, test 14)
    flat = flatten_loops(nested_tree([OUTER], ctx), RegionKind.MATERIAL, ctx)
    # The CW arc is inscribed: n = ⌈π / Δθ_in⌉ chords, Δθ_in = 4·asin(√(t / 2r)), r = 5 mm.
    steps = math.ceil(math.pi / (4 * math.asin(math.sqrt(t_flat / 10.0))))
    assert _vertices_of(flat, 102).shape[0] in (steps, steps + 1)  # REQ-G2D-106's +1 rule


@pytest.mark.req("REQ-G2D-199", "REQ-G2D-184")
@pytest.mark.parametrize("loop", ["circle", "line_and_arc"])
def test_loops_of_research_test_20_hold_each_joint_once(ctx: Context, loop: str) -> None:
    rows = {"circle": [CIRCLE], "line_and_arc": LINE_AND_ARC}[loop]
    region = flatten_loops(nested_tree([rows], ctx), RegionKind.MATERIAL, ctx).region
    _assert_no_repeats(region.points)
    checked = polygon_region(
        region.points, region.loop_starts, region.source_ids, region.fixed, ctx
    )
    assert checked.ok, checked.diagnostics


@pytest.mark.req("REQ-G2D-200")
def test_each_vertex_carries_the_id_of_the_row_that_starts_there(ctx: Context) -> None:
    region = flatten_loops(nested_tree([LINE_AND_ARC], ctx), RegionKind.MATERIAL, ctx).region
    assert region.source_ids[0] == 100  # the line starts at (0, 0)
    assert tuple(region.points[0]) == (0.0, 0.0)
    assert tuple(region.points[1]) == (10.0, 0.0)  # the arc's P0
    assert (region.source_ids[1:] == 101).all()
    assert not region.fixed.any()


@pytest.mark.req("REQ-G2D-201")
def test_results_are_read_only(ctx: Context) -> None:
    region = flatten_loops(nested_tree([OUTER], ctx), RegionKind.AIR, ctx).region
    for array in (region.points, region.loop_starts, region.source_ids, region.fixed):
        assert not array.flags.writeable


@pytest.mark.req("REQ-G2D-127")
def test_t_comes_from_the_context(ctx: Context) -> None:
    rough = _rough(ctx)
    t_rough = rough.tolerances.flatten_tol_mm
    assert t_rough != ctx.tolerances.flatten_tol_mm
    flat = flatten_loops(nested_tree([OUTER], rough), RegionKind.MATERIAL, rough)
    alone = flatten(_arc(OUTER[2]), t_rough, AirSide.RIGHT, rough)
    np.testing.assert_array_equal(_vertices_of(flat, 102), alone[:-1])


@pytest.mark.req("REQ-G2D-119")
def test_a_reversed_arc_stays_in_air_within_t_and_eps_len(ctx: Context) -> None:
    # Given CW, its arc ending 0.9e-6 mm off its circle of radius 10 (valid, REQ-G2D-042);
    # normalised, the reversed arc takes that P1 as its P0 and so the radius 10 + 0.9e-6.
    off = 0.9e-6
    given = [
        [-10.0, 0.0, 10.0 + off, 0.0, 0.0, 0.0, -math.pi],
        [10.0 + off, 0.0, -10.0, 0.0, NAN, NAN, 0.0],
    ]
    flat = flatten_loops(nested_tree([reversed_loop(given)], ctx), RegionKind.MATERIAL, ctx)
    arc = _vertices_of(flat, 101)
    radii = _radii(arc, (0.0, 0.0))
    t_flat = ctx.tolerances.flatten_tol_mm
    assert radii.min() >= 10.0  # circumscribed, in air outside the true circle of radius 10
    assert radii.max() - 10.0 <= t_flat + ctx.tolerances.length_eps_mm + 4 * math.ulp(10.0)


@pytest.mark.req("REQ-G2D-230")
def test_the_step_limit_reaches_the_kernel(ctx: Context, monkeypatch: pytest.MonkeyPatch) -> None:
    # A circle of radius 1e-4 mm, below t_flat / 2: the cap alone sets the count, 4 steps at π/2.
    tiny = [[1e-4, 0.0, 1e-4, 0.0, 0.0, 0.0, math.tau]]
    tree = nested_tree([tiny], ctx)
    assert flatten_loops(tree, RegionKind.AIR, ctx).region.points.shape[0] == 4
    monkeypatch.setattr("splintercam.geometry2d._loops._MAX_STEP_RAD", math.pi)
    assert flatten_loops(tree, RegionKind.AIR, ctx).region.points.shape[0] == 2


@pytest.mark.req("REQ-G2D-106")
def test_a_step_count_beyond_the_int_range_is_refused(ctx: Context) -> None:
    # Outside the radius precondition of 10^9 mm (DEC-G2D-019): within it every count fits.
    huge = [[1e16, 0.0, 1e16, 0.0, 0.0, 0.0, math.tau]]
    with pytest.raises(ValueError, match="steps"):
        flatten_loops(nested_tree([huge], ctx), RegionKind.AIR, ctx)


@pytest.mark.req("REQ-G2D-231")
def test_flattening_a_region_is_bit_identical_when_repeated(ctx: Context) -> None:
    tree = nested_tree([OUTER, ISLAND], ctx)
    first = flatten_loops(tree, RegionKind.MATERIAL, ctx).region
    again = flatten_loops(tree, RegionKind.MATERIAL, ctx).region
    for a, b in zip(
        (first.points, first.loop_starts, first.source_ids, first.fixed),
        (again.points, again.loop_starts, again.source_ids, again.fixed),
        strict=True,
    ):
        assert a.tobytes() == b.tobytes()


@pytest.mark.req("REQ-G2D-186", "REQ-G2D-119")
@pytest.mark.parametrize("kind", [RegionKind.AIR, RegionKind.MATERIAL])
def test_a_shallow_two_row_loop_keeps_three_vertices(ctx: Context, kind: RegionKind) -> None:
    # A line closed by an arc of sagitta 0.002 mm (bulge 0.0004 on 10 mm), below t_flat at tol =
    # 0.05 mm: inscribed in one step it would leave 2 vertices. Given CCW in a pocket, or CW (a
    # hole) in material, the arc is inscribed.
    rough = _rough(ctx)
    built = arc_from_bulge((10.0, 0.0), (0.0, 0.0), 0.0004, rough)
    arc = built.value
    assert isinstance(arc, Arc)
    rows = [[0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0], [10.0, 0.0, 0.0, 0.0, *arc.centre, arc.sweep_rad]]
    box = [
        [-5.0, -5.0, 15.0, -5.0, NAN, NAN, 0.0],
        [15.0, -5.0, 15.0, 5.0, NAN, NAN, 0.0],
        [15.0, 5.0, -5.0, 5.0, NAN, NAN, 0.0],
        [-5.0, 5.0, -5.0, -5.0, NAN, NAN, 0.0],
    ]
    loops = [rows] if kind is RegionKind.AIR else [box, reversed_loop(rows)]
    flat = flatten_loops(nested_tree(loops, rough), kind, rough).region
    checked = polygon_region(flat.points, flat.loop_starts, flat.source_ids, flat.fixed, rough)
    assert checked.ok, checked.diagnostics
    arc_vertices = flat.points[flat.source_ids == flat.source_ids.max()]
    radius = math.hypot(10.0 - arc.centre[0], 0.0 - arc.centre[1])
    radii = _radii(arc_vertices, arc.centre)
    assert np.abs(radii - radius).max() <= 4 * math.ulp(radius)  # inscribed: on the circle


@pytest.mark.req("REQ-G2D-185", "REQ-G2D-199", "REQ-G2D-200")
@pytest.mark.parametrize("where", [0, 2, 4])
def test_a_zero_length_row_adds_no_vertex(ctx: Context, where: int) -> None:
    square = [
        [0.0, 0.0, 10.0, 0.0, NAN, NAN, 0.0],
        [10.0, 0.0, 10.0, 10.0, NAN, NAN, 0.0],
        [10.0, 10.0, 0.0, 10.0, NAN, NAN, 0.0],
        [0.0, 10.0, 0.0, 0.0, NAN, NAN, 0.0],
    ]
    point = square[where % 4][:2]
    square.insert(where, [*point, *point, NAN, NAN, 0.0])
    region = flatten_loops(nested_tree([square], ctx), RegionKind.AIR, ctx).region
    assert region.points.shape[0] == 4
    _assert_no_repeats(region.points)
    assert 100 + where not in region.source_ids.tolist()  # the empty row starts no edge
