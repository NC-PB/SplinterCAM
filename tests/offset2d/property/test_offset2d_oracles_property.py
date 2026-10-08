# SPDX-License-Identifier: Apache-2.0
"""Property tests of the offset2d oracles (`tests/support/offset2d_oracles.py`) and generators
(`tests/support/offset2d_strategies.py`): the distance against dense samples of the true curves
and against exact rationals, "inside R" against geometry2d's point in region, the offset sets
nested as the definitions nest them, and generated regions within the released requirements.

Like the unit tests beside them, these test the test support and carry no requirement marker.
"""

import math
from fractions import Fraction

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from geometry2d_checks import reversed_loop
from geometry2d_oracles import line_foot, squared_distance
from offset2d_oracles import (
    DistanceBand,
    distance_to_curves,
    in_offset,
    inside_region,
    sample_outside_band,
    true_curve_band_mm,
)
from offset2d_strategies import (
    RegionCase,
    bulged_pocket,
    clearances,
    nested_regions,
    pocket_with_islands,
    regions,
    to_curve_rows,
    touching_island,
)
from splintercam.foundation import TOLERANCE_DEFAULTS, Context, ToleranceSet
from splintercam.geometry2d import CurveRows, PointLocation, RegionKind, loop_tree, point_in_region

# The bound of the oracles' module docstring: 64·ε·S, with ε the unit roundoff of float64.
ROUNDOFF = float(np.finfo(np.float64).eps) / 2
BOUND_FACTOR = 64
SPACING_MM = 0.25  # the step of the dense samples along every curve
SEEDS = st.integers(0, 2**32 - 1)
COORD = st.floats(-1000.0, 1000.0)
# Islands near their wall at the finishing tolerance: gaps from t_topo to 2·t_flat, where the two
# side-correct flattenings can still overlap (research 01, rule 7).
_FINISHING = ToleranceSet.for_operation(TOLERANCE_DEFAULTS["chord_tol_finishing_mm"].default).value
assert _FINISHING is not None
NEAR_GAPS = st.floats(_FINISHING.topology_tol_mm, 2.0 * _FINISHING.flatten_tol_mm)


def _queries(case: RegionCase, grow_mm: float, n: int, seed: int) -> NDArray[np.float64]:
    x0, y0, x1, y1 = case.box
    low, high = (x0 - grow_mm, y0 - grow_mm), (x1 + grow_mm, y1 + grow_mm)
    return np.random.default_rng(seed).uniform(low, high, size=(n, 2))


def _dense(rows: NDArray[np.float64], step_mm: float) -> NDArray[np.float64]:
    """Points on every row at most `step_mm` apart along it; arcs from P0 by their sweep (the
    generators put P1 on the circle)."""
    pieces: list[NDArray[np.float64]] = []
    values: list[list[float]] = rows.tolist()
    for x0, y0, x1, y1, cx, cy, sweep in values:
        if sweep == 0.0:
            k = math.ceil(math.hypot(x1 - x0, y1 - y0) / step_mm) + 1
            s = np.linspace(0.0, 1.0, k)
            pieces.append(np.column_stack([x0 + s * (x1 - x0), y0 + s * (y1 - y0)]))
        else:
            r, a0 = math.hypot(x0 - cx, y0 - cy), math.atan2(y0 - cy, x0 - cx)
            angles = a0 + np.linspace(0.0, sweep, math.ceil(r * abs(sweep) / step_mm) + 1)
            pieces.append(np.column_stack([cx + r * np.cos(angles), cy + r * np.sin(angles)]))
    return np.concatenate(pieces)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(case=regions(), seed=SEEDS)
def test_distance_lies_between_the_dense_samples_and_half_a_step_below(
    ctx: Context, case: RegionCase, seed: int
) -> None:
    """Every sample lies on the curves, so d <= the nearest sample; every curve point lies within
    half a step of a sample, so the nearest sample <= d + step/2."""
    loops = case.curve_rows(ctx)
    q = _queries(case, 5.0, 200, seed)
    samples = _dense(loops.rows, SPACING_MM)
    gaps = np.hypot(q[:, None, 0] - samples[None, :, 0], q[:, None, 1] - samples[None, :, 1])
    nearest = gaps.min(axis=1)
    d = distance_to_curves(q, loops)
    eps = ctx.tolerances.length_eps_mm
    assert (d <= nearest + eps).all()
    assert (nearest <= d + SPACING_MM / 2 + eps).all()


def _bound(*values: float) -> float:
    return BOUND_FACTOR * ROUNDOFF * max(abs(v) for v in values)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(q=st.tuples(COORD, COORD), a=st.tuples(COORD, COORD), b=st.tuples(COORD, COORD))
def test_distance_to_a_line_matches_exact_rationals(
    ctx: Context, q: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> None:
    assume(math.dist(a, b) >= ctx.tolerances.length_eps_mm)  # shorter lines are no curve rows
    rows = np.array([[*a, *b, math.nan, math.nan, 0.0]])
    loops = CurveRows(rows, np.zeros(1, np.int64), np.zeros(1, np.int64))
    _, fx, fy = line_foot(q, a, b)
    exact = math.sqrt(float((Fraction(q[0]) - fx) ** 2 + (Fraction(q[1]) - fy) ** 2))
    assert abs(float(distance_to_curves([q], loops)[0]) - exact) <= _bound(*q, *a, *b)


@given(
    centre=st.tuples(COORD, COORD),
    r=st.floats(0.01, 1000.0),
    start=st.floats(0.0, math.tau),
    sweep=st.floats(0.1, math.tau - 0.1),
    ccw=st.booleans(),
    where=st.floats(0.0, 1.0),
    rho_share=st.floats(0.1, 2.0),
    within=st.booleans(),
)
def test_distance_to_an_arc_matches_exact_rationals(  # noqa: PLR0913 (Hypothesis draws)
    centre: tuple[float, float],
    r: float,
    start: float,
    sweep: float,
    ccw: bool,
    where: float,
    rho_share: float,
    within: bool,
) -> None:
    """Query points 0.05 rad or more inside the sweep (nearest point on the circle) or outside it
    (nearest point an end), so the expected case is clear."""
    phi = sweep if ccw else -sweep
    cx, cy = centre
    p0 = (cx + r * math.cos(start), cy + r * math.sin(start))
    p1 = (cx + r * math.cos(start + phi), cy + r * math.sin(start + phi))
    margin = 0.05
    if within:
        alpha = start + math.copysign(margin + where * (sweep - 2 * margin), phi)
    else:
        alpha = start + math.copysign(sweep + margin + where * (math.tau - sweep - 2 * margin), phi)
    rho = rho_share * r
    q = (cx + rho * math.cos(alpha), cy + rho * math.sin(alpha))
    loops = CurveRows(
        np.array([[*p0, *p1, cx, cy, phi]]), np.zeros(1, np.int64), np.zeros(1, np.int64)
    )
    if within:
        rho2, r2 = squared_distance(q, centre), squared_distance(p0, centre)
        exact = abs(float(rho2 - r2)) / (math.sqrt(float(rho2)) + math.sqrt(float(r2)))
    else:
        exact = min(math.sqrt(float(squared_distance(q, p))) for p in (p0, p1))
    scale = max(abs(v) for v in (*q, *p0, *p1, cx, cy)) + r
    assert abs(float(distance_to_curves([q], loops)[0]) - exact) <= _bound(scale)


GENERATORS = {
    "nested": nested_regions(),
    "islands": pocket_with_islands(),
    "bulged": bulged_pocket(),
    "touching": touching_island(),
    "near": touching_island(NEAR_GAPS),
}


@pytest.mark.parametrize("name", list(GENERATORS))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(data=st.data(), seed=SEEDS)
def test_generated_regions_are_valid_and_inside_matches_geometry2d(
    ctx: Context, name: str, data: st.DataObject, seed: int
) -> None:
    """Each generator stays within the released requirements: the loop tree keeps every loop and
    reports nothing. geometry2d's point in region, a separate implementation (REQ-G2D-134), agrees
    with `inside_region` away from the curves, on the loops as drawn and as normalised."""
    case = data.draw(GENERATORS[name])
    loops = case.curve_rows(ctx)
    built = loop_tree(loops, ctx)
    assert built.ok, built.diagnostics
    assert not built.diagnostics
    assert built.value is not None
    tree = built.value.loops
    assert tree.row_starts.size == len(case.loops)
    q = _queries(case, 2.0, 200, seed)
    q = q[distance_to_curves(q, loops) > ctx.tolerances.topology_tol_mm]
    expected = point_in_region(q, tree, ctx) == PointLocation.IN
    assert np.array_equal(inside_region(q, loops), expected)
    assert np.array_equal(inside_region(q, tree), expected)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(case=regions(), t=clearances(), shrink=st.floats(0.0, 1.0), seed=SEEDS)
def test_offsets_nest_as_the_definitions_nest_them(
    ctx: Context, case: RegionCase, t: float, shrink: float, seed: int
) -> None:
    """SHRINK(t) ⊆ R ⊆ GROW(t), each monotone in t, and neither depends on the loops'
    orientation (research 02, Definitions)."""
    loops = case.curve_rows(ctx)
    flipped = to_curve_rows([reversed_loop(loop) for loop in case.loops], ctx)
    q = _queries(case, t, 500, seed)
    smaller = shrink * t
    inside = inside_region(q, loops)
    for kind in (RegionKind.AIR, RegionKind.MATERIAL):
        assert np.array_equal(in_offset(q, loops, kind, t), in_offset(q, flipped, kind, t))
    assert not (in_offset(q, loops, RegionKind.AIR, t) & ~inside).any()
    assert not (inside & ~in_offset(q, loops, RegionKind.MATERIAL, t)).any()
    shrunk_less = in_offset(q, loops, RegionKind.AIR, smaller)
    assert not (in_offset(q, loops, RegionKind.AIR, t) & ~shrunk_less).any()
    grown_less = in_offset(q, loops, RegionKind.MATERIAL, smaller)
    assert not (grown_less & ~in_offset(q, loops, RegionKind.MATERIAL, t)).any()


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(case=regions(), t=clearances(), seed=SEEDS)
def test_sampled_points_lie_in_the_box_outside_the_band(
    ctx: Context, case: RegionCase, t: float, seed: int
) -> None:
    loops = case.curve_rows(ctx)
    band = DistanceBand(t, true_curve_band_mm(ctx.tolerances))
    x0, y0, x1, y1 = case.box
    box = (x0 - t - 1.0, y0 - t - 1.0, x1 + t + 1.0, y1 + t + 1.0)
    q = sample_outside_band(loops, band, box, 300, seed)
    assert q.shape == (300, 2)
    assert (q >= box[:2]).all()
    assert (q <= box[2:]).all()
    assert not band.holds(distance_to_curves(q, loops)).any()
