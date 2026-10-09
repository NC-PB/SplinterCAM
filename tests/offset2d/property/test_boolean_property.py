# SPDX-License-Identifier: Apache-2.0
"""Property test of `boolean`: research 02's Boolean oracle (test 2) on random regions of lines
and arcs with islands, one of them shifted so the two overlap."""

import os

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from numpy.typing import NDArray

from geometry2d_checks import codes
from offset2d_oracles import (
    DistanceBand,
    boolean_band_mm,
    both_operands,
    in_boolean,
    polygon_rows,
    sample_outside_band,
)
from offset2d_strategies import RegionCase, regions
from splintercam.foundation import TOLERANCE_DEFAULTS, Context
from splintercam.geometry2d import PointLocation, PolygonRegion, build_region, point_in_region
from splintercam.offset2d import BooleanOp, EdgeClass, SourceClasses, boolean

N_POINTS = 10_000  # research 02, test 2
EXAMPLES = 1000 if os.environ.get("HYPOTHESIS_PROFILE") == "thorough" else 10  # tests/conftest.py


def _region(
    case: RegionCase, shift: tuple[float, float], id_offset: int, ctx: Context
) -> PolygonRegion:
    built = build_region(case.curve_rows(ctx), case.kind, ctx)
    assert built.value is not None, codes(built)
    region = built.value.region
    moved = region.points + np.array(shift)
    return PolygonRegion(moved, region.loop_starts, region.source_ids + id_offset, region.fixed)


def _segment_distances(
    q: NDArray[np.float64], a: NDArray[np.float64], b: NDArray[np.float64]
) -> NDArray[np.float64]:
    """Per point of q its distance to the nearest of the segments a → b."""
    d = b - a
    length2 = np.maximum((d * d).sum(axis=1), 1e-300)
    t = np.clip(((q[:, None, :] - a[None]) * d[None]).sum(axis=2) / length2, 0.0, 1.0)
    nearest = a[None] + t[:, :, None] * d[None]
    return np.sqrt(((q[:, None, :] - nearest) ** 2).sum(axis=2)).min(axis=1)


def _check_ids_and_fixed(
    result: PolygonRegion, operands: tuple[PolygonRegion, PolygonRegion], ctx: Context
) -> None:
    """Each output edge's middle lies within the reach (6u) of an operand edge carrying its ID
    (REQ-OFF-034, 035); a vertex is fixed exactly where two output vertices share a point (036)."""
    if result.points.shape[0] == 0:
        return
    margin = TOLERANCE_DEFAULTS["rounding_margin_grid_units"].default * ctx.tolerances.grid_unit_mm
    rows = polygon_rows(result.points, result.loop_starts).rows
    middles = (rows[:, 0:2] + rows[:, 2:4]) / 2.0
    for source in np.unique(result.source_ids).tolist():
        starts: list[NDArray[np.float64]] = []
        ends: list[NDArray[np.float64]] = []
        for op in operands:
            if op.loop_starts.size == 0:
                continue
            op_rows = polygon_rows(op.points, op.loop_starts).rows
            mask = op.source_ids == source
            starts.append(op_rows[mask, 0:2])
            ends.append(op_rows[mask, 2:4])
        a, b = np.concatenate(starts), np.concatenate(ends)
        assert a.shape[0] > 0
        mine = middles[result.source_ids == source]
        assert _segment_distances(mine, a, b).max() <= margin
    _, inverse, counts = np.unique(result.points, axis=0, return_inverse=True, return_counts=True)
    shared = counts[inverse.reshape(-1)] > 1
    assert np.array_equal(result.fixed.astype(bool), shared)


def _inside(points: np.ndarray, region: PolygonRegion, ctx: Context) -> np.ndarray:
    if region.loop_starts.size == 0:
        return np.zeros(points.shape[0], dtype=bool)
    rows = polygon_rows(region.points, region.loop_starts)
    return np.asarray(point_in_region(points, rows, ctx) == PointLocation.IN)


@pytest.mark.req("REQ-OFF-030", "REQ-OFF-034", "REQ-OFF-035", "REQ-OFF-036")
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
    max_examples=EXAMPLES,
)
@given(
    cases=st.tuples(regions(), regions(), st.lists(st.booleans(), min_size=1, max_size=64)),
    shift=st.tuples(st.floats(-40.0, 40.0), st.floats(-30.0, 30.0)),
    op=st.sampled_from(list(BooleanOp)),
    seed=st.integers(0, 2**32 - 1),
)
def test_points_outside_the_band_follow_the_operation(
    ctx: Context,
    cases: tuple[RegionCase, RegionCase, list[bool]],
    shift: tuple[float, float],
    op: BooleanOp,
    seed: int,
) -> None:
    """At 10^4 points farther than 3u from every edge of either operand, the result holds a point
    exactly when op(inside a, inside b) does (research 02, test 2; the Vatti note's oracle); the
    IDs and fixed flags hold as `_check_ids_and_fixed` says, with edges of material and air drawn
    at random; and union and intersection give the same arrays with the operands swapped."""
    a, b = _region(cases[0], (0.0, 0.0), 0, ctx), _region(cases[1], shift, 10_000, ctx)
    air = cases[2]  # per source ID, cyclically: whether its edge bounds air
    ids = np.unique(np.concatenate([a.source_ids, b.source_ids]))
    tags = np.array([air[i % len(air)] for i in range(ids.size)], dtype=bool)
    kinds = np.where(tags, int(EdgeClass.AIR), int(EdgeClass.MATERIAL)).astype(np.int8)
    classes = SourceClasses(ids, kinds)
    result = boolean(a, b, op, classes, ctx)
    assert result.value is not None, codes(result)
    corners = np.concatenate([a.points, b.points])
    low, high = corners.min(axis=0) - 1.0, corners.max(axis=0) + 1.0
    box = (float(low[0]), float(low[1]), float(high[0]), float(high[1]))
    edges = both_operands(
        polygon_rows(a.points, a.loop_starts), polygon_rows(b.points, b.loop_starts)
    )
    band = DistanceBand(0.0, boolean_band_mm(ctx.tolerances))
    points = sample_outside_band(edges, band, box, N_POINTS, seed)
    expected = in_boolean(op.name, _inside(points, a, ctx), _inside(points, b, ctx))
    assert np.array_equal(_inside(points, result.value, ctx), expected)
    _check_ids_and_fixed(result.value, (a, b), ctx)
    if op is not BooleanOp.DIFFERENCE:
        swapped = boolean(b, a, op, classes, ctx).value
        assert swapped is not None
        assert swapped.points.tobytes() == result.value.points.tobytes()
        assert swapped.fixed.tobytes() == result.value.fixed.tobytes()
        assert swapped.source_ids.tobytes() == result.value.source_ids.tobytes()
