# SPDX-License-Identifier: Apache-2.0
"""Property test: the topology flattening stays within u on the inside of every arc (research 01,
Loop tree, rule 1)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from geometry2d_checks import loop
from splintercam.foundation import Context
from splintercam.geometry2d import AirSide, Arc, arc_from_bulge, flatten, polygon_region
from splintercam.geometry2d._loops import topology_flattening

NAN = math.nan


@st.composite
def _loops(draw: st.DrawFn) -> list[list[float]]:
    """A loop of 4 to 8 lines and arcs (bulges of either sign) around a random centre."""
    n = draw(st.integers(4, 8))
    cx, cy = draw(st.floats(-1000.0, 1000.0)), draw(st.floats(-1000.0, 1000.0))
    radius = draw(st.floats(1.0, 50.0))
    jitter = draw(st.lists(st.floats(-0.2, 0.2), min_size=n, max_size=n))
    bulges = draw(st.lists(st.floats(-1.0, 1.0), min_size=n, max_size=n))
    step = math.tau / n
    points = [
        (cx + radius * math.cos((k + j) * step), cy + radius * math.sin((k + j) * step))
        for k, j in enumerate(jitter)
    ]
    return [
        [*p0, *p1, b] for p0, p1, b in zip(points, points[1:] + points[:1], bulges, strict=True)
    ]


# The ctx fixture holds a progress log and a debug sink that every example shares; the topology
# flattening uses neither, so sharing it is safe here.
@pytest.mark.req("REQ-G2D-152", "REQ-G2D-184", "REQ-G2D-199", "REQ-G2D-240")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(drawn=_loops())
def test_every_arc_is_inscribed_within_u(ctx: Context, drawn: list[list[float]]) -> None:
    rows: list[list[float]] = []
    for x0, y0, x1, y1, bulge in drawn:
        built = arc_from_bulge((x0, y0), (x1, y1), bulge, ctx)
        assert built.value is not None, built.diagnostics
        curve = built.value
        if isinstance(curve, Arc):
            rows.append([x0, y0, x1, y1, *curve.centre, curve.sweep_rad])
        else:
            rows.append([x0, y0, x1, y1, NAN, NAN, 0.0])
    region = topology_flattening(loop(rows, ctx), ctx)
    checked = polygon_region(
        region.points, region.loop_starts, region.source_ids, region.fixed, ctx
    )
    assert checked.ok, checked.diagnostics

    u = ctx.tolerances.grid_unit_mm
    closed = np.vstack([region.points, region.points[:1]])
    for row_id, (x0, y0, x1, y1, cx, cy, sweep) in enumerate(rows):
        mine = region.source_ids == row_id
        if sweep == 0.0:
            assert mine.sum() == 1
            continue
        arc = Arc((x0, y0), (x1, y1), (cx, cy), sweep)
        assert (
            mine.sum()
            == flatten(arc, u, AirSide.LEFT if sweep > 0 else AirSide.RIGHT, ctx).shape[0] - 1
        )
        radius = math.hypot(x0 - cx, y0 - cy)
        # sin and cos within 4 units of 1 move a vertex by 4·r·ulp(1); adding C rounds twice more.
        bound = 4 * radius * math.ulp(1.0) + 2 * math.ulp(abs(cx) + abs(cy) + radius)
        vertices = region.points[mine]
        assert np.abs(np.hypot(vertices[:, 0] - cx, vertices[:, 1] - cy) - radius).max() <= bound
        index = np.flatnonzero(mine)
        middles = (closed[index] + closed[index + 1]) / 2
        middle_radii = np.hypot(middles[:, 0] - cx, middles[:, 1] - cy)
        # P1 may lie a little off the circle: the last chord ends there (REQ-G2D-110).
        p1_off = abs(math.hypot(x1 - cx, y1 - cy) - radius)
        assert middle_radii.max() <= radius + bound + p1_off  # inside
        assert middle_radii.min() >= radius - u - bound - p1_off  # within u
