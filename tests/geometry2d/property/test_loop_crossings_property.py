# SPDX-License-Identifier: Apache-2.0
"""Property tests of the depth rule (REQ-G2D-237): touching curves never cross, overlaps deeper
than 2·t_topo always do (SPEC, Test plan)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from geometry2d_checks import codes, polygons
from splintercam.foundation import Context
from splintercam.geometry2d import curve_rows
from splintercam.geometry2d._screen import screen_loops


@pytest.mark.req("REQ-G2D-237", "REQ-G2D-163")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(
    outer=st.floats(5.0, 50.0),
    ratio=st.floats(0.1, 0.8),
    touch=st.floats(0.0, math.tau),
    starts=st.tuples(st.floats(0.0, math.tau), st.floats(0.0, math.tau)),
)
def test_a_circle_tangent_inside_another_touches(
    ctx: Context, outer: float, ratio: float, touch: float, starts: tuple[float, float]
) -> None:
    inner = outer * ratio
    cx, cy = (outer - inner) * math.cos(touch), (outer - inner) * math.sin(touch)
    rows: list[list[float]] = []
    for (x, y, r), start in zip(((0.0, 0.0, outer), (cx, cy, inner)), starts, strict=True):
        p = (x + r * math.cos(start), y + r * math.sin(start))
        rows.append([*p, *p, x, y, math.tau])
    built = curve_rows(
        np.array(rows), np.arange(2, dtype=np.int64), np.array([0, 1], np.int64), ctx
    )
    assert built.value is not None, built.diagnostics
    result = screen_loops(built.value, ctx)
    assert "LOOPS_CROSS" not in codes(result)


@pytest.mark.req("REQ-G2D-237")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(depth_t_topo=st.floats(2.5, 1e4), y0=st.floats(1.0, 4.0), height=st.floats(1.0, 4.0))
def test_a_poke_deeper_than_twice_t_topo_crosses(
    ctx: Context, depth_t_topo: float, y0: float, height: float
) -> None:
    depth = depth_t_topo * ctx.tolerances.topology_tol_mm
    poke = [(5.0, y0), (10.0 + depth, y0), (10.0 + depth, y0 + height), (5.0, y0 + height)]
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    result = screen_loops(polygons([square, poke], ctx), ctx)
    assert codes(result) == ["LOOPS_CROSS"]
