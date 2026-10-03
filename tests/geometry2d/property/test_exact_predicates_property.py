# SPDX-License-Identifier: Apache-2.0
"""Property tests: the predicates against exact rationals, on nearly degenerate input (research 01,
Vectors and exact signs; Shewchuk note, test ideas 1 and 3)."""

import numpy as np
import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

import geometry2d_oracles as oracle
from splintercam import _kernels
from splintercam.geometry2d import in_arc_circle, incircle, orient2d

coordinate = st.floats(-100.0, 100.0)
point = st.tuples(coordinate, coordinate)
# Nudges of a few rounding units make the points nearly collinear or cocircular.
nudge = st.integers(-4, 4)


@st.composite
def near_collinear(draw: st.DrawFn) -> tuple[tuple[float, float], ...]:
    a, b = draw(point), draw(point)
    t = draw(st.floats(-2.0, 3.0))
    c = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
    steps = draw(nudge), draw(nudge)
    c = (c[0] + steps[0] * np.spacing(c[0]), c[1] + steps[1] * np.spacing(c[1]))
    return a, b, (float(c[0]), float(c[1]))


def _one(*points: tuple[float, float]) -> list[np.ndarray]:
    return [np.array([p]) for p in points]


@pytest.mark.req("REQ-G2D-007", "REQ-G2D-009", "REQ-G2D-010")
@given(near_collinear())
def test_orient2d_is_exact_antisymmetric_and_cyclic(
    points: tuple[tuple[float, float], ...],
) -> None:
    a, b, c = points
    assume(oracle.in_safe_range(*a, *b, *c))
    s = int(orient2d(*_one(a, b, c))[0])
    assert s == oracle.orient2d(a, b, c)
    assert int(orient2d(*_one(b, a, c))[0]) == -s  # swapped
    assert int(orient2d(*_one(b, c, a))[0]) == s  # shifted
    assert int(orient2d(*_one(c, a, b))[0]) == s


@pytest.mark.req("REQ-G2D-011")
@given(
    point,
    st.floats(0.0, 6.3),
    st.floats(0.0, 6.3),
    st.floats(0.0, 6.3),
    st.floats(0.01, 50.0),
    nudge,
    nudge,
)
def test_incircle_is_exact(  # noqa: PLR0913 (Hypothesis draws)
    centre: tuple[float, float], ta: float, tb: float, td: float, r: float, nx: int, ny: int
) -> None:
    # Four points on one circle up to rounding, d then nudged by a few rounding units: nearly
    # cocircular, so the adaptive stages beyond the first are reached.
    def on_circle(t: float) -> tuple[float, float]:
        return (float(centre[0] + r * np.cos(t)), float(centre[1] + r * np.sin(t)))

    a, b, c = on_circle(ta), on_circle(tb), on_circle(ta + tb)
    dx, dy = on_circle(td)
    d = (float(dx + nx * np.spacing(dx)), float(dy + ny * np.spacing(dy)))
    assume(oracle.in_safe_range(*a, *b, *c, *d))
    assert int(incircle(*_one(a, b, c, d))[0]) == oracle.incircle(a, b, c, d)


@pytest.mark.req("REQ-G2D-022")
@given(point, point, st.floats(0.0, 6.3), nudge, nudge)
def test_in_arc_circle_is_exact(
    centre: tuple[float, float], p0: tuple[float, float], angle: float, nx: int, ny: int
) -> None:
    # q on the circle through p0 about centre, then nudged by a few rounding units.
    r = float(np.hypot(p0[0] - centre[0], p0[1] - centre[1]))
    qx, qy = centre[0] + r * np.cos(angle), centre[1] + r * np.sin(angle)
    q = (float(qx + nx * np.spacing(qx)), float(qy + ny * np.spacing(qy)))
    assume(oracle.in_safe_range(*q, *centre, *p0))
    assert int(in_arc_circle(*_one(q, centre, p0))[0]) == oracle.in_arc_circle(q, centre, p0)


@pytest.mark.req("REQ-G2D-023")
@given(point, point, nudge)
def test_vertical_extent_sign_is_exact(
    centre: tuple[float, float], p0: tuple[float, float], n: int
) -> None:
    r = float(np.hypot(p0[0] - centre[0], p0[1] - centre[1]))
    top = centre[1] + r
    q_y = float(top + n * np.spacing(top))
    assume(oracle.in_safe_range(q_y, *centre, *p0))
    out = np.empty(1, dtype=np.int8)
    _kernels.geometry2d.vertical_extent_signs(
        np.array([q_y]), np.array([centre]), np.array([p0]), out
    )
    from fractions import Fraction

    dy = Fraction(q_y) - Fraction(centre[1])
    assert int(out[0]) == oracle.sign(dy * dy - oracle.squared_distance(p0, centre))
