# SPDX-License-Identifier: Apache-2.0
"""Property test: flattened arcs stay within t on their side (research 01, Flattening)."""

import math

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from splintercam.foundation import Context
from splintercam.geometry2d import AirSide, Arc, flatten


# The ctx fixture holds a progress log and a debug sink that every example shares; flatten uses
# neither, so sharing it is safe here.
@pytest.mark.req("REQ-G2D-106", "REQ-G2D-110", "REQ-G2D-112")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    r=st.floats(0.01, 1000.0),
    start=st.floats(-math.pi, math.pi),
    sweep=st.floats(0.01, math.tau).flatmap(lambda s: st.sampled_from([s, -s])),
    t=st.floats(1e-5, 0.1),
    side=st.sampled_from([AirSide.LEFT, AirSide.RIGHT]),
)
def test_flattening_stays_within_t_on_its_side(  # noqa: PLR0913 (Hypothesis draws)
    ctx: Context, r: float, start: float, sweep: float, t: float, side: AirSide
) -> None:
    p0 = (r * math.cos(start), r * math.sin(start))
    p1 = (r * math.cos(start + sweep), r * math.sin(start + sweep))
    points = flatten(Arc(p0, p1, (0.0, 0.0), sweep), t, side, ctx)
    assert (tuple(points[0]), tuple(points[-1])) == (p0, p1)
    s = np.linspace(0.0, 1.0, 64)[:, None, None]
    along = points[:-1] + s * (points[1:] - points[:-1])
    radii = np.hypot(along[..., 0], along[..., 1])
    slack = 8 * math.ulp(r)  # the rounding of the vertices and of the end points on the circle
    assert radii.max() <= r + t + slack
    assert radii.min() >= r - t - slack
    inscribed = (side is AirSide.LEFT) == (sweep > 0)
    if inscribed:
        assert radii.max() <= r + slack
    else:
        assert radii.min() >= r - slack
