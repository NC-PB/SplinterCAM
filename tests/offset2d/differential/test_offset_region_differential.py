# SPDX-License-Identifier: Apache-2.0
"""Research 02's test 20: `offset_region` against shapely/GEOS buffers with round joins, compared
as point sets outside the band (D-060, ADR 0010), on test 10's random regions and tolerances.

GEOS is a reference nobody here wrote: its buffer shares neither Clipper2's algorithm nor our
reading of the definitions (the oracles of tests 2 and 9 do). Its own error is bounded and added
to the band: the true curves are densified with sagitta s before GEOS sees them, which moves the
offset by at most 2s (`dense_loops`), and GEOS draws round joins with `quad_segs` chords per
quarter circle, whose sagitta t·(1 - cos(π/(4·quad_segs))) is held below s. Points within
t ± (a + 6u + t_flat + 3s) of the true curves are not compared.
"""

import dataclasses
import functools
import math
import os

import numpy as np
import pytest
import shapely
from hypothesis import HealthCheck, given, reject, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from geometry2d_checks import codes
from offset2d_oracles import (
    DistanceBand,
    dense_loops,
    polygon_rows,
    sample_outside_band,
    true_curve_band_mm,
)
from offset2d_strategies import RegionCase, clearances, regions
from splintercam.foundation import Context, ToleranceSet
from splintercam.geometry2d import CurveRows, PointLocation, RegionKind, point_in_region
from splintercam.offset2d import EdgeClass, SourceClasses, offset_region

N_POINTS = 10_000  # research 02, tests 9 and 10
# As test 10 (test_offset_region_property.py): a tenth of the profile's examples, since Clipper2's
# inward offset of dense input at tol_min costs up to about a second.
EXAMPLES = 1000 if os.environ.get("HYPOTHESIS_PROFILE") == "thorough" else 10  # tests/conftest.py
TOLERANCES_MM = [0.01, 0.0022858, 0.05]  # tol, tol_min, roughing (D-146), as test 10


def _with_tol(ctx: Context, tol_mm: float) -> Context:
    built = ToleranceSet.for_operation(tol_mm)
    assert built.value is not None, built.diagnostics
    return dataclasses.replace(ctx, tolerances=built.value)


def _quad_segs(t_mm: float, sagitta_mm: float) -> int:
    """Chords per quarter circle so that a round join of radius t has sagitta at most s."""
    return max(8, math.ceil(math.pi / (4.0 * math.acos(1.0 - min(1.0, sagitta_mm / t_mm)))))


def _reference(
    loops: CurveRows, kind: RegionKind, t_mm: float, sagitta_mm: float
) -> shapely.Geometry:
    """GEOS's offset: R as the even-odd union of the densified loops (the loops are simple and do
    not cross, so nesting alternates), shrunk by t for air, grown by t for material."""
    rings = [shapely.Polygon(ring) for ring in dense_loops(loops, sagitta_mm)]
    # Pairwise: shapely deprecates symmetric_difference_all (shapely issue 2027).
    region = functools.reduce(shapely.symmetric_difference, rings)
    signed = -t_mm if kind is RegionKind.AIR else t_mm
    return shapely.buffer(
        region, signed, quad_segs=_quad_segs(t_mm, sagitta_mm), join_style="round"
    )


@pytest.mark.req("REQ-OFF-020", "REQ-OFF-022", "REQ-OFF-025")
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=EXAMPLES,
)
@given(
    case=regions(),
    t_mm=clearances(),
    tol_mm=st.sampled_from(TOLERANCES_MM),
    seed=st.integers(0, 2**32 - 1),
)
def test_the_offset_agrees_with_geos_outside_the_band(
    ctx: Context, case: RegionCase, t_mm: float, tol_mm: float, seed: int
) -> None:
    """Research 02, test 20: every sampled point farther than the band (widened by GEOS's own
    error) from the clearance t of the true curves lies in our result exactly when it lies in
    GEOS's round-joined buffer of the same region (REQ-OFF-020, 022)."""
    ctx = _with_tol(ctx, tol_mm)
    sagitta = ctx.tolerances.grid_unit_mm  # GEOS's error at u: far below the band, cheap enough
    loops = case.curve_rows(ctx)
    ids = np.unique(loops.ids)
    classes = SourceClasses(ids, np.full(ids.size, int(EdgeClass.MATERIAL), dtype=np.int8))
    result = offset_region(loops, case.kind, t_mm, classes, ctx)
    assert result.value is not None, codes(result)
    ours = result.value
    reference = _reference(loops, case.kind, t_mm, sagitta)

    x0, y0, x1, y1 = case.box
    grow = t_mm if case.kind is RegionKind.MATERIAL else 0.0
    box = (x0 - grow - 1.0, y0 - grow - 1.0, x1 + grow + 1.0, y1 + grow + 1.0)
    band = DistanceBand(t_mm, true_curve_band_mm(ctx.tolerances) + 3.0 * sagitta)
    try:
        points = sample_outside_band(loops, band, box, N_POINTS, seed)
    except ValueError:
        reject()  # a box almost wholly within the band; Hypothesis reports it if frequent
    shapely.prepare(reference)
    expected: NDArray[np.bool_] = shapely.contains_xy(reference, points[:, 0], points[:, 1])
    if ours.points.shape[0] == 0:
        assert not expected.any()
        return
    located = point_in_region(points, polygon_rows(ours.points, ours.loop_starts), ctx)
    disagree = np.flatnonzero((located == PointLocation.IN) != expected)
    assert disagree.size == 0, points[disagree[:5]]
