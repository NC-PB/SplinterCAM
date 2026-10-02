# SPDX-License-Identifier: Apache-2.0
"""Unit tests for flattening with a known error side (research 01, Flattening; test 4)."""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from splintercam.foundation import TOLERANCE_DEFAULTS, Context
from splintercam.geometry2d import AirSide, Arc, Line, flatten

R, T = 10.0, 0.001  # research 01, test 4
CIRCLE = Arc((R, 0.0), (R, 0.0), (0.0, 0.0), math.tau)
ROUNDING = 4 * math.ulp(R)  # test 4: up to 4 rounding units of the radius


def _radii(points: NDArray[np.float64], samples: int = 10_000) -> NDArray[np.float64]:
    """Distances from the origin of `samples` points on each segment of the polyline."""
    s = np.linspace(0.0, 1.0, samples)[:, None, None]
    along = points[:-1] + s * (points[1:] - points[:-1])
    return np.hypot(along[..., 0], along[..., 1]).ravel()


@pytest.mark.req("REQ-G2D-102", "REQ-G2D-103", "REQ-G2D-106", "REQ-G2D-110", "REQ-G2D-112")
def test_inscribed_full_circle_of_research_test_4(ctx: Context) -> None:
    points = flatten(CIRCLE, T, AirSide.LEFT, ctx)
    assert points.shape == (224, 2)  # 223 chords
    assert tuple(points[0]) == tuple(points[-1]) == CIRCLE.p0
    radii = _radii(points)
    assert radii.max() <= R + ROUNDING
    assert radii.min() >= R - T - ROUNDING
    assert np.abs(np.hypot(points[:, 0], points[:, 1]) - R).max() <= ROUNDING  # vertices on the arc


@pytest.mark.req("REQ-G2D-104", "REQ-G2D-105", "REQ-G2D-106", "REQ-G2D-110", "REQ-G2D-112")
def test_circumscribed_full_circle_of_research_test_4(ctx: Context) -> None:
    points = flatten(CIRCLE, T, AirSide.RIGHT, ctx)
    assert points.shape == (225, 2)  # 224 segments, the first and last half tangents
    assert tuple(points[0]) == tuple(points[-1]) == CIRCLE.p0
    radii = _radii(points)
    assert radii.min() >= R - ROUNDING
    assert radii.max() <= R + T + ROUNDING
    # The half tangents at P0 = (10, 0) are vertical: P0 -> v0 and v_last -> P0.
    assert points[1, 0] == pytest.approx(R, abs=ROUNDING)
    assert points[-2, 0] == pytest.approx(R, abs=ROUNDING)


@pytest.mark.req("REQ-G2D-106", "REQ-G2D-103")
def test_steps_are_spread_evenly(ctx: Context) -> None:
    arc = Arc((R, 0.0), (0.0, R), (0.0, 0.0), -3 * math.pi / 2)  # CW from 0 to pi/2
    points = flatten(arc, T, None, ctx)
    angles = np.unwrap(np.arctan2(points[:, 1], points[:, 0]))
    steps = np.diff(angles)
    n = len(steps)
    assert np.allclose(steps, -1.5 * math.pi / n, rtol=0.0, atol=1e-12)


@pytest.mark.req("REQ-G2D-109", "REQ-G2D-230")
def test_tolerance_above_the_diameter_gives_four_chords_per_circle(ctx: Context) -> None:
    points = flatten(Arc((1.0, 0.0), (1.0, 0.0), (0.0, 0.0), math.tau), 5.0, None, ctx)
    assert points.shape == (5, 2)
    assert np.isfinite(points).all()
    assert TOLERANCE_DEFAULTS["flatten_step_max_rad"].default == math.pi / 2


@pytest.mark.req("REQ-G2D-113")
@pytest.mark.parametrize(
    ("sweep", "side", "inscribed"),
    [
        (math.pi, AirSide.LEFT, True),  # CCW: the centre lies left, on the air side
        (math.pi, AirSide.RIGHT, False),
        (-math.pi, AirSide.RIGHT, True),  # CW: the centre lies right
        (-math.pi, AirSide.LEFT, False),
    ],
)
def test_side_decides_the_form(ctx: Context, sweep: float, side: AirSide, inscribed: bool) -> None:
    arc = Arc((R, 0.0), (-R, 0.0), (0.0, 0.0), sweep)
    radii = _radii(flatten(arc, T, side, ctx), samples=101)
    if inscribed:
        assert radii.max() <= R + ROUNDING
    else:
        assert radii.min() >= R - ROUNDING


@pytest.mark.req("REQ-G2D-126")
def test_no_side_flattens_inscribed(ctx: Context) -> None:
    arc = Arc((R, 0.0), (-R, 0.0), (0.0, 0.0), math.pi)
    np.testing.assert_array_equal(flatten(arc, T, None, ctx), flatten(arc, T, AirSide.LEFT, ctx))


@pytest.mark.req("REQ-G2D-110")
def test_last_segment_reaches_a_p1_off_the_circle(ctx: Context) -> None:
    # P1 lies 0.5 eps_len outside the circle (a valid arc); the last chord ends there exactly.
    p1 = (0.0, R + 5e-7)
    points = flatten(Arc((R, 0.0), p1, (0.0, 0.0), math.pi / 2), T, None, ctx)
    assert tuple(points[-1]) == p1
    assert _radii(points[:-1]).max() <= R + ROUNDING


@pytest.mark.req("REQ-G2D-112")
def test_line_flattens_to_its_end_points(ctx: Context) -> None:
    points = flatten(Line((0.1, 0.2), (3.0, 4.0)), T, AirSide.LEFT, ctx)
    assert points.tolist() == [[0.1, 0.2], [3.0, 4.0]]
    assert not points.flags.writeable


@pytest.mark.req("REQ-G2D-102")
@pytest.mark.parametrize("t", [0.0, -1.0, math.nan, math.inf])
def test_tolerance_must_be_positive_and_finite(ctx: Context, t: float) -> None:
    with pytest.raises(ValueError, match="t_mm"):
        flatten(CIRCLE, t, None, ctx)


@pytest.mark.req("REQ-G2D-231")
@pytest.mark.parametrize("side", [AirSide.LEFT, AirSide.RIGHT])
def test_flattening_is_bit_identical_when_repeated(ctx: Context, side: AirSide) -> None:
    first = flatten(CIRCLE, T, side, ctx)
    assert flatten(CIRCLE, T, side, ctx).tobytes() == first.tobytes()
