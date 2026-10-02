# SPDX-License-Identifier: Apache-2.0
"""Property test: arcs built from bulges have their centre on the bisector (research 01, Curves)."""

import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from splintercam.foundation import Context
from splintercam.geometry2d import arc_from_bulge

coordinate = st.floats(-1000.0, 1000.0)


# The ctx fixture holds a progress log and a debug sink that every example shares;
# arc_from_bulge uses neither, so sharing it is safe here.
@pytest.mark.req("REQ-G2D-044")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    x0=coordinate,
    y0=coordinate,
    direction=st.floats(-math.pi, math.pi),
    chord=st.floats(1e-3, 1e3),
    size=st.floats(1e-3, 1e3),
    sense=st.sampled_from([1.0, -1.0]),
)
def test_arcs_from_bulges_are_never_inconsistent(  # noqa: PLR0913 (Hypothesis draws)
    ctx: Context, x0: float, y0: float, direction: float, chord: float, size: float, sense: float
) -> None:
    p1 = (x0 + chord * math.cos(direction), y0 + chord * math.sin(direction))
    result = arc_from_bulge((x0, y0), p1, sense * size, ctx)
    assert result.ok, result.diagnostics
