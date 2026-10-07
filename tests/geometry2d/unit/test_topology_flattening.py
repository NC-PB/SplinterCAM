# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the topology flattening (research 01, Loop tree, rule 1) and the kernel's sine
and cosine from IEEE basic operations (SPEC, determinism note)."""

import dataclasses
import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import loop, reversed_loop
from splintercam import _kernels
from splintercam.foundation import Context, ToleranceSet
from splintercam.geometry2d._loops import topology_flattening

R = 10.0
CIRCLE = [[R, 0.0, R, 0.0, 0.0, 0.0, math.tau]]


def _sin_cos(angles: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    s, c = np.empty_like(angles), np.empty_like(angles)
    _kernels.geometry2d.basic_sin_cos(angles, s, c)
    return s, c


@pytest.mark.req("REQ-G2D-240")
def test_basic_sine_and_cosine_at_zero_and_the_quadrant_points() -> None:
    s, c = _sin_cos(np.array([0.0, -0.0]))
    assert s.tolist() == [0.0, -0.0]
    assert c.tolist() == [1.0, 1.0]
    quadrants = np.array([math.pi / 2, math.pi, 3 * math.pi / 2, -math.pi / 2])
    s, c = _sin_cos(quadrants)
    assert s[0] == 1.0
    assert s[2] == -1.0
    assert s[3] == -1.0
    assert c[1] == -1.0
    # The doubles nearest the quadrant points are not on them: the other value is the tiny offset
    # (about 6e-17), within REQ-G2D-240's 4 rounding units of 1 like every value.
    bound = 4 * math.ulp(1.0)
    np.testing.assert_allclose(c[[0, 2, 3]], np.cos(quadrants[[0, 2, 3]]), rtol=0, atol=bound)
    assert abs(s[1] - math.sin(math.pi)) <= bound


@pytest.mark.req("REQ-G2D-240", "REQ-G2D-018")
def test_basic_sine_and_cosine_follow_libm_within_rounding() -> None:
    angles = np.linspace(-2 * math.tau, 2 * math.tau, 40_001)
    s, c = _sin_cos(angles)
    # The reduction by π/2 is exact to half a unit of r; the Horner sums cost a few units of 1.
    bound = 4 * math.ulp(1.0)
    assert np.abs(s - np.sin(angles)).max() <= bound
    assert np.abs(c - np.cos(angles)).max() <= bound
    assert np.abs(s * s + c * c - 1.0).max() <= bound


@pytest.mark.req("REQ-G2D-240")
@pytest.mark.parametrize("angle", [math.nan, math.inf, 4 * math.pi * (1 + 2**-50)])
def test_angles_beyond_4_pi_are_refused(angle: float) -> None:
    with pytest.raises(ValueError, match="4π"):
        _sin_cos(np.array([angle]))


def _radii(
    points: NDArray[np.float64], centre: tuple[float, float] = (0.0, 0.0)
) -> NDArray[np.float64]:
    return np.hypot(points[:, 0] - centre[0], points[:, 1] - centre[1])


# Turning P0 - C by sin and cos within 4 rounding units of 1 moves a vertex by up to about
# 4·R·ulp(1); adding C rounds once more.
def _on_circle(radius: float, centre_scale: float) -> float:
    return 4 * radius * math.ulp(1.0) + 2 * math.ulp(radius + centre_scale)


@pytest.mark.req("REQ-G2D-152", "REQ-G2D-029")
def test_a_circle_is_flattened_inscribed_within_u(ctx: Context) -> None:
    u = ctx.tolerances.grid_unit_mm
    region = topology_flattening(loop(CIRCLE, ctx), ctx)
    points = region.points
    steps = math.ceil(math.tau / (4 * math.asin(math.sqrt(u / (2 * R)))))
    assert points.shape[0] in (steps, steps + 1)  # REQ-G2D-106's +1 rule
    assert np.abs(_radii(points) - R).max() <= _on_circle(R, 0.0)  # vertices on the circle
    following = np.roll(points, -1, axis=0)
    middles = (points + following) / 2
    assert _radii(middles).min() >= R - u - _on_circle(R, 0.0)  # chords within u, inside


@pytest.mark.req("REQ-G2D-152")
def test_vertices_match_the_libm_flattening_within_rounding(ctx: Context) -> None:
    from splintercam.geometry2d import AirSide, Arc, flatten

    u = ctx.tolerances.grid_unit_mm
    region = topology_flattening(loop(CIRCLE, ctx), ctx)
    alone = flatten(Arc((R, 0.0), (R, 0.0), (0.0, 0.0), math.tau), u, AirSide.LEFT, ctx)
    assert region.points.shape[0] == alone.shape[0] - 1
    assert np.abs(region.points - alone[:-1]).max() <= 2 * _on_circle(R, 0.0)  # both off by that


@pytest.mark.req("REQ-G2D-029")
def test_the_grid_unit_comes_from_the_context(ctx: Context) -> None:
    class _Coarse(ToleranceSet):
        @property
        def grid_unit_mm(self) -> float:
            return 100 * super().grid_unit_mm

    coarse = dataclasses.replace(
        ctx,
        tolerances=_Coarse(
            ctx.tolerances.chord_tol_mm,
            ctx.tolerances.length_eps_mm,
            ctx.tolerances.angle_eps_rad,
            ctx.tolerances.stage_shares,
        ),
    )
    fine = topology_flattening(loop(CIRCLE, ctx), ctx).points.shape[0]
    rough = topology_flattening(loop(CIRCLE, coarse), coarse).points.shape[0]
    assert rough < fine


@pytest.mark.req("REQ-G2D-152", "REQ-G2D-018")
def test_vertices_are_pinned_bit_for_bit(ctx: Context) -> None:
    region = topology_flattening(loop(CIRCLE, ctx), ctx)
    picked = [region.points[k].tolist() for k in (1, 2, 100, 351, 500)]
    assert [[x.hex() for x in p] for p in picked] == PINNED


# Pinned on macOS (2026-10-08) from the implementation; CI on Linux and Windows must give the same
# bits, since the kernel's sine and cosine use IEEE basic operations only (D-055, tier 1).
PINNED = [
    ["0x1.3ffcba61bd2dep+3", "0x1.6e1510643806ap-4"],
    ["0x1.3ff2e99815be6p+3", "0x1.6e11522678b55p-3"],
    ["0x1.90f27a8feb8dep+2", "0x1.f2d70af88365ep+2"],
    ["-0x1.3fff2e982ac73p+3", "0x1.6e15fff493058p-5"],
    ["-0x1.34ac5892bb933p+1", "-0x1.368e5879e50e8p+3"],
]

NAN = math.nan
# A line along y = 5 closed by a CW half circle below it about (25, 5): off-centre and clockwise.
OFF_CENTRE = [[20.0, 5.0, 30.0, 5.0, NAN, NAN, 0.0], [30.0, 5.0, 20.0, 5.0, 25.0, 5.0, -math.pi]]
PINNED_CW = [
    ["0x1.dff97aeac3f98p+4", "0x1.37ed139e2a3ccp+2"],
    ["0x1.4f65c2b4e5e6ep+4", "0x1.068319ba323c4p+1"],
]


@pytest.mark.req("REQ-G2D-152", "REQ-G2D-199", "REQ-G2D-200", "REQ-G2D-018")
@pytest.mark.parametrize("reverse", [False, True])
def test_an_off_centre_clockwise_arc_and_a_line(ctx: Context, reverse: bool) -> None:
    rows = reversed_loop(OFF_CENTRE) if reverse else OFF_CENTRE
    region = topology_flattening(loop(rows, ctx), ctx)
    assert region.loop_starts.tolist() == [0]
    line_id, arc_id = (1, 0) if reverse else (0, 1)
    assert region.source_ids.tolist().count(line_id) == 1  # the line adds its P0 only
    arc = region.points[region.source_ids == arc_id]
    u = ctx.tolerances.grid_unit_mm
    bound = _on_circle(5.0, 25.0)
    assert np.abs(_radii(arc, (25.0, 5.0)) - 5.0).max() <= bound
    loop_points = np.vstack([region.points, region.points[:1]])
    middles = (loop_points[:-1] + loop_points[1:]) / 2
    arc_middles = middles[region.source_ids == arc_id]
    assert _radii(arc_middles, (25.0, 5.0)).min() >= 5.0 - u - bound  # within u, inside
    if not reverse:
        picked = [[x.hex() for x in region.points[k].tolist()] for k in (3, 200)]
        assert picked == PINNED_CW
