# SPDX-License-Identifier: Apache-2.0
"""Property tests: arcs built from bulges have their centre on the bisector and are valid up to the
radius limit (research 01, Curves)."""

import math

import pytest
from hypothesis import HealthCheck, assume, example, given, settings
from hypothesis import strategies as st

from splintercam.foundation import Context
from splintercam.geometry2d import Arc, arc_from_bulge

coordinate = st.floats(-1000.0, 1000.0)


# The ctx fixture holds a progress log and a debug sink that every example shares;
# arc_from_bulge uses neither, so sharing it is safe here.
@pytest.mark.req("REQ-G2D-044", "REQ-G2D-039")
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
    assert result.value is not None
    assert (result.value.p0, result.value.p1) == ((x0, y0), p1)  # the end points as given


@pytest.mark.req("REQ-G2D-042", "REQ-G2D-043", "REQ-G2D-044")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    x0=st.floats(-3000.0, 3000.0),
    y0=st.floats(-3000.0, 3000.0),
    direction=st.floats(-math.pi, math.pi),
    chord=st.floats(0.1, 2000.0),
    radius=st.floats(1e3, 1e9),  # up to the radius precondition (DEC-G2D-019)
    major=st.booleans(),
    sense=st.sampled_from([1.0, -1.0]),
)
@example(x0=3000.0, y0=3000.0, direction=0.0, chord=2000.0, radius=1e9, major=False, sense=1.0)
@example(x0=3000.0, y0=3000.0, direction=0.0, chord=2000.0, radius=1e9, major=True, sense=1.0)
def test_arcs_up_to_the_radius_limit_are_never_inconsistent(  # noqa: PLR0913 (Hypothesis draws)
    ctx: Context,
    x0: float,
    y0: float,
    direction: float,
    chord: float,
    radius: float,
    major: bool,
    sense: float,
) -> None:
    # The minor or the major arc on the chord; the major one has a sweep near 2π, where the
    # angle check binds (DEC-G2D-019).
    half = math.asin(chord / (2 * radius))
    sweep = 2 * math.pi - 2 * half if major else 2 * half
    assume(major or chord * math.tan(sweep / 4) / 2 > ctx.tolerances.length_eps_mm)  # no line
    p1 = (x0 + chord * math.cos(direction), y0 + chord * math.sin(direction))
    result = arc_from_bulge((x0, y0), p1, sense * math.tan(sweep / 4), ctx)
    assert result.ok, result.diagnostics
    assert isinstance(result.value, Arc)
