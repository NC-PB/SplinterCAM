# SPDX-License-Identifier: Apache-2.0
"""Property tests of `offset_region`: research 02's band (test 10) and its offset oracle (test 9),
on random regions of lines and arcs with islands, the touching island of test 21 among them (the
orientation guard, REQ-OFF-023), at tol 0.01 mm, tol_min and 0.05 mm (D-146)."""

import dataclasses
import os

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from geometry2d_checks import codes
from offset2d_oracles import (
    DistanceBand,
    distance_to_curves,
    in_offset,
    offset_band_mm,
    polygon_rows,
    sample_outside_band,
    true_curve_band_mm,
)
from offset2d_strategies import RegionCase, regions
from splintercam.foundation import TOLERANCE_DEFAULTS, Context, ToleranceSet
from splintercam.geometry2d import (
    CurveRows,
    PointLocation,
    PolygonRegion,
    RegionKind,
    flatten_loops,
    loop_tree,
    point_in_region,
)
from splintercam.offset2d import EdgeClass, SourceClasses, offset_region

N_POINTS = 10_000  # research 02, tests 9 and 10
# A tenth of the profile's examples (10 of the dev profile's 100, 1000 of thorough's 10,000):
# at tol_min arcs flatten into thousands of segments, and Clipper2's inward offset past an arc's
# radius costs up to about a second (measured 2026-10-09: 2100 vertices shrunk by 10 mm, 640 ms;
# research 02: dense input is to be reduced first), so a normal run takes about 2 to 3 s a test.
EXAMPLES = 1000 if os.environ.get("HYPOTHESIS_PROFILE") == "thorough" else 10  # tests/conftest.py
TOLERANCES_MM = [0.01, 0.0022858, 0.05]  # tol, tol_min (a at its floor of 2u), roughing (D-146)

cases = regions()


def _with_tol(ctx: Context, tol_mm: float) -> Context:
    built = ToleranceSet.for_operation(tol_mm)
    assert built.value is not None, built.diagnostics
    return dataclasses.replace(ctx, tolerances=built.value)


def _offset(case: RegionCase, t_mm: float, ctx: Context) -> tuple[CurveRows, PolygonRegion]:
    loops = case.curve_rows(ctx)
    ids = np.unique(loops.ids)
    classes = SourceClasses(ids, np.full(ids.size, int(EdgeClass.MATERIAL), dtype=np.int8))
    result = offset_region(loops, case.kind, t_mm, classes, ctx)
    assert result.value is not None, codes(result)
    assert "OFFSET_FAILED" not in codes(result)
    return loops, result.value


@pytest.mark.req("REQ-OFF-025", "REQ-OFF-022", "REQ-OFF-034")
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=EXAMPLES,
)
@given(case=cases, t_mm=st.floats(0.1, 50.0), tol_mm=st.sampled_from(TOLERANCES_MM))
def test_every_boundary_point_lies_in_the_band(
    ctx: Context, case: RegionCase, t_mm: float, tol_mm: float
) -> None:
    """Research 02, test 10: every output vertex and edge midpoint lies between t and t + a + 6u
    from the flattened input (REQ-OFF-025)."""
    ctx = _with_tol(ctx, tol_mm)
    loops, region = _offset(case, t_mm, ctx)
    tree = loop_tree(loops, ctx).value
    assert tree is not None
    flat = flatten_loops(tree, case.kind, ctx).region
    if region.points.shape[0] == 0:
        return
    rows = polygon_rows(region.points, region.loop_starts)
    probes = np.concatenate([region.points, (rows.rows[:, 0:2] + rows.rows[:, 2:4]) / 2.0])
    d = distance_to_curves(probes, polygon_rows(flat.points, flat.loop_starts))
    assert d.min() >= t_mm - 1e-9 * max(1.0, t_mm)  # the oracle's own error bound, far below u
    assert d.max() <= t_mm + offset_band_mm(ctx.tolerances)
    # Each edge's own source edge lies in the band too (REQ-OFF-034, research 02, test 10),
    # measured against the true curve of that row, so within [t, t + a + 6u + t_flat].
    middles = (rows.rows[:, 0:2] + rows.rows[:, 2:4]) / 2.0
    top = t_mm + true_curve_band_mm(ctx.tolerances)
    for source in np.unique(region.source_ids).tolist():
        row = loops.rows[loops.ids == source]
        alone = CurveRows(row, np.array([source]), np.array([0], dtype=np.int64))
        to_source = distance_to_curves(middles[region.source_ids == source], alone)
        assert to_source.min() >= t_mm - 1e-9 * max(1.0, t_mm)  # the oracle's own error bound
        assert to_source.max() <= top


@pytest.mark.req("REQ-OFF-020", "REQ-OFF-023", "REQ-OFF-026")
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=EXAMPLES,
)
@given(
    case=cases,
    t_mm=st.floats(0.1, 50.0),
    tol_mm=st.sampled_from(TOLERANCES_MM),
    seed=st.integers(0, 2**32 - 1),
)
def test_points_outside_the_band_are_classified_as_the_definition_says(
    ctx: Context, case: RegionCase, t_mm: float, tol_mm: float, seed: int
) -> None:
    """Research 02, test 9: at points farther than the band from the clearance t of the true
    lines and arcs, p lies in the result exactly when p ∈ R and d(p, B) ≥ t (air), or p ∈ R or
    d(p, R) ≤ t (material) (REQ-OFF-020)."""
    ctx = _with_tol(ctx, tol_mm)
    loops, region = _offset(case, t_mm, ctx)
    x0, y0, x1, y1 = case.box
    grow = t_mm if case.kind is RegionKind.MATERIAL else 0.0
    box = (x0 - grow - 1.0, y0 - grow - 1.0, x1 + grow + 1.0, y1 + grow + 1.0)
    band = DistanceBand(t_mm, true_curve_band_mm(ctx.tolerances))
    try:
        points = sample_outside_band(loops, band, box, N_POINTS, seed)
    except ValueError:
        return  # a region whose box lies almost wholly within the band: nothing to sample
    expected = in_offset(points, loops, case.kind, t_mm)
    if region.points.shape[0] == 0:
        assert not expected.any()
        return
    # The result read by geometry2d's point in region (REQ-G2D-133 ff.); the expected side stays
    # the independent oracle. Points outside the band lie far from the result's boundary.
    located = point_in_region(points, polygon_rows(region.points, region.loop_starts), ctx)
    assert np.array_equal(located == PointLocation.IN, expected)


@pytest.mark.req("REQ-OFF-010")
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=EXAMPLES,
)
@given(case=cases, t_mm=st.floats(0.1, 50.0), tol_mm=st.sampled_from(TOLERANCES_MM))
def test_a_translated_region_gives_the_translated_result(
    ctx: Context, case: RegionCase, t_mm: float, tol_mm: float
) -> None:
    """Research 02, test 17: moved by (10 000, -10 000) mm and back, the same topology and every
    vertex within 3u of the other result's boundary, except near a critical distance, where the
    grid decides the topology (REQ-OFF-026). Measured to the boundary, not vertex to vertex: a
    round join's steps start where the rounded corner puts them, so the two results can hold a
    different number of join vertices (DEC-OFF-013)."""
    ctx = _with_tol(ctx, tol_mm)
    shift = np.array([10_000.0, -10_000.0])
    moved_loops = [
        [[r[0] + shift[0], r[1] + shift[1], r[2] + shift[0], r[3] + shift[1],
          r[4] + shift[0], r[5] + shift[1], r[6]] for r in loop]
        for loop in case.loops
    ]  # fmt: skip
    _, here = _offset(case, t_mm, ctx)
    _, there = _offset(RegionCase(moved_loops, case.kind), t_mm, ctx)
    if here.loop_starts.size != there.loop_starts.size:
        # Only near a critical distance may the grid decide the topology (REQ-OFF-026): then the
        # loop count must change within the rounding margin of t (6u) at the origin too.
        margin = (
            TOLERANCE_DEFAULTS["rounding_margin_grid_units"].default * ctx.tolerances.grid_unit_mm
        )
        counts = {_offset(case, t, ctx)[1].loop_starts.size for t in (t_mm - margin, t_mm + margin)}
        assert counts != {here.loop_starts.size}
        return
    if here.points.shape[0] == 0:
        return
    back = there.points - shift
    limit = 3.0 * ctx.tolerances.grid_unit_mm
    assert distance_to_curves(here.points, polygon_rows(back, there.loop_starts)).max() <= limit
    assert distance_to_curves(back, polygon_rows(here.points, here.loop_starts)).max() <= limit
