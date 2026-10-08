# SPDX-License-Identifier: Apache-2.0
"""Known answers for the offset2d oracles (`tests/support/offset2d_oracles.py`): research 02's
annulus (test 6), rectangle (test 7), strait (Held test 4) and squares (test 1), arcs and their
ends, the sampler and the SPEC's bands.

These test the test support, not offset2d, so they carry no requirement marker: a marker would
let traceability count REQ-OFF-020, 025 or 030 as verified before any offset2d code exists. The
offset2d tests that use these oracles carry the markers.
"""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import polygon, reversed_loop
from offset2d_oracles import (
    BooleanName,
    DistanceBand,
    arc_tol_mm,
    boolean_band_mm,
    both_operands,
    distance_to_curves,
    in_boolean,
    in_offset,
    inside_region,
    offset_band_mm,
    polygon_rows,
    sample_outside_band,
    true_curve_band_mm,
)
from offset2d_strategies import circle, rounded_box, to_curve_rows
from splintercam.foundation import Context, ToleranceSet
from splintercam.geometry2d import CurveRows, RegionKind, flatten_loops, loop_tree

N_POINTS = 4000  # sampled points per known answer; research 02's 10^4 is for the offset tests
NAN = math.nan


def _annulus(ctx: Context, flip: bool = False) -> CurveRows:
    """Held test 1: wall radius 20 CCW, island radius 10 CW, same centre (research 02, test 6)."""
    wall, island = circle(0.0, 0.0, 20.0, 0.0, 1), reversed_loop(circle(0.0, 0.0, 10.0, 0.0, 1))
    loops = [reversed_loop(wall), reversed_loop(island)] if flip else [wall, island]
    return to_curve_rows(loops, ctx)


def _band(ctx: Context, t_mm: float) -> DistanceBand:
    return DistanceBand(t_mm, true_curve_band_mm(ctx.tolerances))


def _rows(rows: list[list[float]]) -> CurveRows:
    """Rows as one open set of curves, unchecked: the distance needs no closed loop."""
    array = np.array(rows, dtype=np.float64)
    return CurveRows(array, np.arange(len(rows), dtype=np.int64), np.zeros(1, np.int64))


@pytest.mark.parametrize("flip", [False, True])
def test_annulus_shrunk_by_3_is_the_ring_from_13_to_17(ctx: Context, flip: bool) -> None:
    loops = _annulus(ctx, flip)
    q = sample_outside_band(loops, _band(ctx, 3.0), (-22.0, -22.0, 22.0, 22.0), N_POINTS, 6)
    r = np.hypot(q[:, 0], q[:, 1])
    expected = (r >= 13.0) & (r <= 17.0)
    assert expected.any()
    assert ((r > 10.0) & (r < 20.0) & ~expected).any()  # in R but not in the offset
    assert np.array_equal(in_offset(q, loops, RegionKind.AIR, 3.0), expected)


def test_annulus_shrunk_by_8_is_empty(ctx: Context) -> None:
    loops = _annulus(ctx)
    q = sample_outside_band(loops, _band(ctx, 8.0), (-22.0, -22.0, 22.0, 22.0), N_POINTS, 8)
    r = np.hypot(q[:, 0], q[:, 1])
    assert np.array_equal(inside_region(q, loops), (r > 10.0) & (r < 20.0))
    assert not in_offset(q, loops, RegionKind.AIR, 8.0).any()


def _rectangle(ctx: Context) -> CurveRows:
    """Research 02, test 7: [0, 100] x [0, 60]."""
    return polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 60.0), (0.0, 60.0)], ctx)


def _in_box(
    q: NDArray[np.float64], x0: float, y0: float, x1: float, y1: float
) -> NDArray[np.bool_]:
    return (q[:, 0] >= x0) & (q[:, 0] <= x1) & (q[:, 1] >= y0) & (q[:, 1] <= y1)


def test_rectangle_shrunk_by_10_is_the_inner_rectangle(ctx: Context) -> None:
    loops = _rectangle(ctx)
    q = sample_outside_band(loops, _band(ctx, 10.0), (-5.0, -5.0, 105.0, 65.0), N_POINTS, 7)
    expected = _in_box(q, 10.0, 10.0, 90.0, 50.0)
    assert expected.any()
    assert np.array_equal(in_offset(q, loops, RegionKind.AIR, 10.0), expected)


def test_rectangle_shrunk_by_30_is_empty(ctx: Context) -> None:
    loops = _rectangle(ctx)
    q = sample_outside_band(loops, _band(ctx, 30.0), (-5.0, -5.0, 105.0, 65.0), N_POINTS, 30)
    assert _in_box(q, 0.0, 0.0, 100.0, 60.0).any()
    assert not in_offset(q, loops, RegionKind.AIR, 30.0).any()


def test_rectangle_of_material_grown_by_10_is_the_rounded_rectangle(ctx: Context) -> None:
    loops = _rectangle(ctx)
    q = sample_outside_band(loops, _band(ctx, 10.0), (-15.0, -15.0, 115.0, 75.0), N_POINTS, 10)
    outside_x = np.maximum(np.maximum(-q[:, 0], q[:, 0] - 100.0), 0.0)
    outside_y = np.maximum(np.maximum(-q[:, 1], q[:, 1] - 60.0), 0.0)
    expected = np.hypot(outside_x, outside_y) <= 10.0
    assert (expected & ~_in_box(q, 0.0, 0.0, 100.0, 60.0)).any()
    assert np.array_equal(in_offset(q, loops, RegionKind.MATERIAL, 10.0), expected)


STRAIT = [
    (0.0, 0.0),
    (44.0, 0.0),
    (50.0, 12.0),
    (56.0, 0.0),
    (100.0, 0.0),
    (100.0, 40.0),
    (56.0, 40.0),
    (50.0, 28.0),
    (44.0, 40.0),
    (0.0, 40.0),
]


def test_strait_of_width_8_joins_at_7_9_and_splits_at_8_1(ctx: Context) -> None:
    """Held test 4 (research 02, test 8) by sampled points: d is 1-Lipschitz, so samples a step h
    apart with d beyond t ± h/2 decide every point of the segment between them."""
    loops = polygon(STRAIT, ctx)
    h = 0.01
    across = np.column_stack([np.arange(25.0, 75.0 + h / 2, h), np.full(5001, 20.0)])
    assert in_offset(across, loops, RegionKind.AIR, 7.9).all()
    assert distance_to_curves(across, loops).min() - h / 2 >= 7.9  # one path joins both sides

    through = np.column_stack([np.full(4001, 50.0), np.arange(0.0, 40.0 + h / 2, h)])
    sides = np.array([[25.0, 20.0], [75.0, 20.0]])
    assert in_offset(sides, loops, RegionKind.AIR, 8.1).all()
    assert not in_offset(through, loops, RegionKind.AIR, 8.1).any()
    inside = inside_region(through, loops)
    assert distance_to_curves(through[inside], loops).max() + h / 2 < 8.1  # x = 50 separates them


SQUARES = {"a": (0.0, 10.0), "b": (5.0, 15.0)}  # research 02, test 1


def _square(ctx: Context, side: tuple[float, float]) -> CurveRows:
    lo, hi = side
    return polygon([(lo, lo), (hi, lo), (hi, hi), (lo, hi)], ctx)


@pytest.mark.parametrize(
    ("op", "area"), [("INTERSECTION", 25.0), ("UNION", 175.0), ("DIFFERENCE", 75.0)]
)
def test_booleans_of_the_squares_of_test_1_have_their_areas(
    ctx: Context, op: BooleanName, area: float
) -> None:
    h = 0.1  # cell centres 0.05 from every edge, so the count is exact
    ticks = np.arange(-1.0 + h / 2, 16.0, h)
    q = np.stack(np.meshgrid(ticks, ticks), axis=-1).reshape(-1, 2)
    a, b = _square(ctx, SQUARES["a"]), _square(ctx, SQUARES["b"])
    kept = in_boolean(op, inside_region(q, a), inside_region(q, b))
    assert math.isclose(np.count_nonzero(kept) * h * h, area, abs_tol=h * h / 2)


@pytest.mark.parametrize("op", ["INTERSECTION", "UNION", "DIFFERENCE"])
def test_boolean_oracle_matches_the_squares_outside_the_3u_band(
    ctx: Context, op: BooleanName
) -> None:
    a, b = _square(ctx, SQUARES["a"]), _square(ctx, SQUARES["b"])
    band = DistanceBand(0.0, boolean_band_mm(ctx.tolerances))
    q = sample_outside_band(both_operands(a, b), band, (-1.0, -1.0, 16.0, 16.0), N_POINTS, 2)
    in_a, in_b = _in_box(q, 0.0, 0.0, 10.0, 10.0), _in_box(q, 5.0, 5.0, 15.0, 15.0)
    expected = {"INTERSECTION": in_a & in_b, "UNION": in_a | in_b, "DIFFERENCE": in_a & ~in_b}[op]
    assert np.array_equal(in_boolean(op, inside_region(q, a), inside_region(q, b)), expected)


def test_in_boolean_is_the_truth_table() -> None:
    a, b = np.array([False, False, True, True]), np.array([False, True, False, True])
    assert in_boolean("UNION", a, b).tolist() == [False, True, True, True]
    assert in_boolean("DIFFERENCE", a, b).tolist() == [False, False, True, False]
    assert in_boolean("INTERSECTION", a, b).tolist() == [False, False, False, True]


QUARTER = [10.0, 0.0, 0.0, 10.0, 0.0, 0.0, math.pi / 2]  # CCW from (10, 0) to (0, 10)


@pytest.mark.parametrize("rows", [[QUARTER], reversed_loop([QUARTER])])
def test_distance_to_an_arc_is_to_its_circle_within_the_sweep_else_to_an_end(
    ctx: Context, rows: list[list[float]]
) -> None:
    q = np.array([[3.0, 4.0], [12.0, 16.0], [0.0, 0.0], [-6.0, 10.0], [-5.0, -5.0], [10.0, -3.0]])
    expected = [5.0, 10.0, 10.0, 6.0, math.hypot(15.0, 5.0), 3.0]
    eps = ctx.tolerances.length_eps_mm
    assert distance_to_curves(q, _rows(rows)) == pytest.approx(expected, abs=eps)


def test_distance_includes_the_radial_connector_to_p1_off_the_circle(ctx: Context) -> None:
    off = [10.0, 0.0, 0.0, 10.5, 0.0, 0.0, math.pi / 2]  # P1 0.5 beyond the circle of radius 10
    q = np.array([[0.0, 10.5], [-1.0, 10.25], [0.0, 12.0]])
    eps = ctx.tolerances.length_eps_mm
    assert distance_to_curves(q, _rows([off])) == pytest.approx([0.0, 1.0, 1.5], abs=eps)


def test_a_full_circle_is_at_its_radius_from_its_centre(ctx: Context) -> None:
    loops = to_curve_rows([circle(1.0, 2.0, 7.0, 0.4, 1)], ctx)
    eps = ctx.tolerances.length_eps_mm
    assert distance_to_curves([[1.0, 2.0]], loops) == pytest.approx([7.0], abs=eps)
    assert inside_region([[1.0, 2.0], [9.0, 2.0]], loops).tolist() == [True, False]


@pytest.mark.parametrize("start", [0.0, math.pi / 2])
def test_points_on_the_chords_of_a_circle_in_halves_are_inside(ctx: Context, start: float) -> None:
    """Both chords run through the centre, so these points lie on a chord's line, where the
    polygon and the circular segments must break the tie alike."""
    loops = to_curve_rows([circle(0.0, 0.0, 10.0, start, 2)], ctx)
    q = [[3.0, 0.0], [-3.0, 0.0], [0.0, 0.0], [0.0, 3.0], [0.0, -3.0], [11.0, 0.0], [0.0, 11.0]]
    assert inside_region(q, loops).tolist() == [True] * 5 + [False] * 2
    assert (
        inside_region(
            q, to_curve_rows([reversed_loop(circle(0.0, 0.0, 10.0, start, 2))], ctx)
        ).tolist()
        == [True] * 5 + [False] * 2
    )


D_RIGHT = [  # a half disc right of x = 0 joined to [-5, 0] x [-10, 10]
    [0.0, -10.0, 0.0, 10.0, 0.0, 0.0, math.pi],
    [0.0, 10.0, -5.0, 10.0, NAN, NAN, 0.0],
    [-5.0, 10.0, -5.0, -10.0, NAN, NAN, 0.0],
    [-5.0, -10.0, 0.0, -10.0, NAN, NAN, 0.0],
]
D_LEFT = [  # a half disc left of x = 0 joined to [0, 5] x [-10, 10]
    [0.0, 10.0, 0.0, -10.0, 0.0, 0.0, math.pi],
    [0.0, -10.0, 5.0, -10.0, NAN, NAN, 0.0],
    [5.0, -10.0, 5.0, 10.0, NAN, NAN, 0.0],
    [5.0, 10.0, 0.0, 10.0, NAN, NAN, 0.0],
]
D_UP = [  # a half disc above y = 0 joined to [-10, 10] x [-5, 0]: a horizontal chord
    [10.0, 0.0, -10.0, 0.0, 0.0, 0.0, math.pi],
    [-10.0, 0.0, -10.0, -5.0, NAN, NAN, 0.0],
    [-10.0, -5.0, 10.0, -5.0, NAN, NAN, 0.0],
    [10.0, -5.0, 10.0, 0.0, NAN, NAN, 0.0],
]
ON_VERTICAL_CHORD = [[0.0, 3.0], [0.0, -3.0], [0.0, 0.0], [0.0, 9.0], [12.0, 0.0], [-12.0, 0.0]]
ON_HORIZONTAL_CHORD = [[3.0, 0.0], [-3.0, 0.0], [0.0, 0.0], [9.0, 0.0], [0.0, 12.0], [0.0, -7.0]]


@pytest.mark.parametrize(
    ("rows", "q"),
    [
        (D_RIGHT, ON_VERTICAL_CHORD),
        (reversed_loop(D_RIGHT), ON_VERTICAL_CHORD),
        (D_LEFT, ON_VERTICAL_CHORD),
        (reversed_loop(D_LEFT), ON_VERTICAL_CHORD),
        (D_UP, ON_HORIZONTAL_CHORD),
        (reversed_loop(D_UP), ON_HORIZONTAL_CHORD),
    ],
)
def test_points_on_the_chord_line_of_one_arc_are_inside(
    ctx: Context, rows: list[list[float]], q: list[list[float]]
) -> None:
    """The arc's chord runs through the region's interior, and only that arc's segment can hold
    these points: the polygon and the segment must break the tie on the chord's line alike."""
    assert inside_region(q, to_curve_rows([rows], ctx)).tolist() == [True] * 4 + [False] * 2


def test_rays_through_the_vertices_of_the_annulus_count_each_loop_once(ctx: Context) -> None:
    q = [[15.0, 0.0], [-15.0, 0.0], [5.0, 0.0], [25.0, 0.0], [0.0, 15.0]]
    assert inside_region(q, _annulus(ctx)).tolist() == [True, True, False, False, True]


def test_rounded_corners_bound_the_region_and_its_distance(ctx: Context) -> None:
    loops = to_curve_rows([rounded_box(0.0, 0.0, 90.0, 60.0, 10.0)], ctx)
    q = [[1.0, 1.0], [5.0, 5.0], [45.0, 30.0], [-1.0, 30.0]]
    assert inside_region(q, loops).tolist() == [False, True, True, False]
    corner_gap = 10.0 * math.sqrt(2.0) - 10.0
    eps = ctx.tolerances.length_eps_mm
    assert distance_to_curves([[0.0, 0.0]], loops) == pytest.approx([corner_gap], abs=eps)


def test_polygon_rows_close_each_loop_of_a_polygon_region() -> None:
    points = [
        (0.0, 0.0),
        (4.0, 0.0),
        (4.0, 4.0),
        (0.0, 4.0),
        (1.0, 1.0),
        (1.0, 3.0),
        (3.0, 3.0),
        (3.0, 1.0),
    ]
    loops = polygon_rows(points, [0, 4])
    q = [[0.5, 2.0], [2.0, 2.0], [5.0, 2.0]]
    assert inside_region(q, loops).tolist() == [True, False, False]
    assert distance_to_curves([[2.0, -1.0], [2.0, 2.0]], loops) == pytest.approx([1.0, 1.0])


def test_sampler_is_seeded_and_keeps_n_points_in_the_box_outside_the_band(ctx: Context) -> None:
    loops, band, box = _annulus(ctx), DistanceBand(3.0, 0.5), (-22.0, -21.0, 23.0, 24.0)
    q = sample_outside_band(loops, band, box, 5000, 11)
    assert q.shape == (5000, 2)
    assert np.array_equal(q, sample_outside_band(loops, band, box, 5000, 11))
    assert not np.array_equal(q, sample_outside_band(loops, band, box, 5000, 12))
    assert (q >= [-22.0, -21.0]).all()
    assert (q <= [23.0, 24.0]).all()
    assert not band.holds(distance_to_curves(q, loops)).any()


def test_sampler_refuses_a_band_that_covers_the_box(ctx: Context) -> None:
    with pytest.raises(ValueError, match="outside"):
        sample_outside_band(_annulus(ctx), DistanceBand(5.0, 50.0), (-1.0, -1.0, 1.0, 1.0), 10, 0)


@pytest.mark.parametrize("t_mm", [-0.1, math.nan, math.inf])
def test_in_offset_refuses_a_clearance_that_is_negative_or_not_finite(
    ctx: Context, t_mm: float
) -> None:
    with pytest.raises(ValueError, match="finite"):
        in_offset([[0.0, 0.0]], _annulus(ctx), RegionKind.AIR, t_mm)


# offset2d SPEC, Requirements, preamble: the three tolerances of test 10; a = max(0.05·tol, 2u)
# takes its floor 2u = 0.0002 mm at tol_min; t_flat = 0.05·tol - 0.0001 - 3·1e-6 mm (foundation).
@pytest.mark.parametrize(
    ("tol_mm", "a_mm", "band_mm", "true_band_mm"),
    [
        (0.01, 0.0005, 0.0011, 0.001497),
        (0.0022858, 0.0002, 0.0008, 0.00081129),
        (0.05, 0.0025, 0.0031, 0.005497),
    ],
)
def test_bands_at_the_three_tolerances_of_test_10(
    tol_mm: float, a_mm: float, band_mm: float, true_band_mm: float
) -> None:
    built = ToleranceSet.for_operation(tol_mm)
    assert built.value is not None, built.diagnostics
    tolerances = built.value
    assert arc_tol_mm(tolerances) == pytest.approx(a_mm, rel=1e-9)
    assert arc_tol_mm(tolerances) == tolerances.arc_tol_mm  # foundation's, REQ-FND-011
    assert offset_band_mm(tolerances) == pytest.approx(band_mm, rel=1e-9)
    assert true_curve_band_mm(tolerances) == pytest.approx(true_band_mm, rel=1e-9)
    assert boolean_band_mm(tolerances) == pytest.approx(0.0003, rel=1e-9)


def test_the_touching_island_of_test_21_flattens_past_the_wall(ctx: Context) -> None:
    """Research 02, test 21: an island of radius 5 tangent inside a wall of radius 20 at its top,
    neither arc starting there; the island's side-correct flattening reaches outside the wall's
    (research 01, rule 7), the case the generator `touching_island` draws."""
    wall = circle(0.0, 0.0, 20.0, 0.3, 1)
    island = reversed_loop(circle(0.0, 15.0, 5.0, 0.3, 1))
    tree = loop_tree(to_curve_rows([wall, island], ctx), ctx)
    assert tree.ok, tree.diagnostics
    assert tree.value is not None
    flat = flatten_loops(tree.value, RegionKind.AIR, ctx).region
    loops = np.split(flat.points, flat.loop_starts[1:])
    flat_wall, flat_island = sorted(loops, key=lambda p: float(np.ptp(p[:, 0])), reverse=True)
    eps = ctx.tolerances.length_eps_mm
    assert np.hypot(flat_island[:, 0], flat_island[:, 1] - 15.0).min() >= 5.0 - eps
    assert not inside_region(flat_island, polygon_rows(flat_wall, [0])).all()
