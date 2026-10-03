# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the exact height comparison with the end of an arc's radial connector (Peter,
2026-10-03): where the ray from C through P1 meets the circle, which is no double in general."""

import math
from decimal import Decimal, localcontext

import pytest

import geometry2d_oracles as oracle
from splintercam import _kernels

ray_height_sign = _kernels.geometry2d.ray_height_sign
P = tuple[float, float]


def _ray_end_height(centre: P, p0: P, toward: P) -> float:
    # The height c_y + r·(t_y - c_y)/|t - c|, rounded once from 60 digits.
    with localcontext() as ctx:
        ctx.prec = 60
        cx, cy, px, py, tx, ty = (Decimal(v) for v in (*centre, *p0, *toward))
        r = ((px - cx) ** 2 + (py - cy) ** 2).sqrt()
        return float(cy + r * (ty - cy) / ((tx - cx) ** 2 + (ty - cy) ** 2).sqrt())


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-005")
@pytest.mark.parametrize(
    ("centre", "p0", "toward"),
    [
        ((0.0, 0.0), (5.0, 0.0), (1.0, 1.0)),
        ((1.5, -2.25), (9.0, 3.0), (-4.0, 7.125)),
        ((10.0, 10.0), (10.0, 13.0), (12.0, 10.0 + 2.0**-30)),
        ((0.3, 0.7), (-11.0, 4.0), (0.31, -5.0)),
    ],
)
def test_the_sign_is_exact_next_to_the_ray_end(centre: P, p0: P, toward: P) -> None:
    # q_y at the double nearest the ray's end and one rounding unit either side: a comparison
    # with a rounded height would get some of them wrong.
    nearest = _ray_end_height(centre, p0, toward)
    for q_y in (math.nextafter(nearest, -math.inf), nearest, math.nextafter(nearest, math.inf)):
        assert ray_height_sign(q_y, centre, p0, toward) == oracle.ray_height_sign(
            q_y, centre, p0, toward
        )
    assert ray_height_sign(math.nextafter(nearest, -math.inf), centre, p0, toward) == -1
    assert ray_height_sign(math.nextafter(nearest, math.inf), centre, p0, toward) == 1


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-005")
def test_straight_above_and_below_the_centre() -> None:
    centre, p0 = (1.0, 2.0), (4.0, 6.0)  # r = 5: top at y = 7, bottom at y = -3
    for toward, end in [((1.0, 10.0), 7.0), ((1.0, -30.0), -3.0)]:
        assert ray_height_sign(end, centre, p0, toward) == 0
        assert ray_height_sign(math.nextafter(end, math.inf), centre, p0, toward) == 1
        assert ray_height_sign(math.nextafter(end, -math.inf), centre, p0, toward) == -1


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-005")
@pytest.mark.parametrize(
    ("q_y", "toward", "expected"),
    [
        (0.5, (3.0, -4.0), 1),  # q above c_y, the ray's end below
        (0.0, (3.0, 4.0), -1),  # q at c_y, the end above
        (-0.5, (3.0, 4.0), -1),  # q below, the end above
        (0.0, (7.0, 0.0), 0),  # both at c_y
        (4.0, (6.0, 8.0), 0),  # the end (3, 4) is a double here
    ],
)
def test_sides_of_the_centre_height(q_y: float, toward: P, expected: int) -> None:
    assert ray_height_sign(q_y, (0.0, 0.0), (5.0, 0.0), toward) == expected
