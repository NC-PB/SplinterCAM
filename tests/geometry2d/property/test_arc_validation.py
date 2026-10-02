# SPDX-License-Identifier: Apache-2.0
"""Property tests for arc validation: arcs built on their circle are accepted and keep P1."""

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from splintercam.foundation import Context
from splintercam.geometry2d import Arc, make_arc

coordinate = st.floats(-1000.0, 1000.0)
radius = st.floats(0.01, 1000.0)
angle = st.floats(-math.pi, math.pi)
# Sweeps away from 0 and 2*pi, so neither the radius rule nor the nearly closed rule applies.
sweep_size = st.floats(0.01, math.tau - 0.01)


@pytest.mark.req("REQ-G2D-039", "REQ-G2D-042", "REQ-G2D-043")
# The Context fixture is immutable, so sharing it across examples is safe.
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    cx=coordinate,
    cy=coordinate,
    r=radius,
    start=angle,
    size=sweep_size,
    sense=st.sampled_from([1.0, -1.0]),
)
def test_arc_built_on_its_circle_is_accepted_and_keeps_p1(  # noqa: PLR0913 (Hypothesis draws)
    ctx: Context, cx: float, cy: float, r: float, start: float, size: float, sense: float
) -> None:
    sweep = sense * size
    p0 = (cx + r * math.cos(start), cy + r * math.sin(start))
    p1 = (cx + r * math.cos(start + sweep), cy + r * math.sin(start + sweep))
    result = make_arc(p0, p1, (cx, cy), sweep, ctx)
    assert result.ok, result.diagnostics
    assert result.value == (Arc(p0, p1, (cx, cy), sweep),)
