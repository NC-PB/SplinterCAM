# SPDX-License-Identifier: Apache-2.0
"""Property test: the exact height comparison with a connector's end against exact rationals
(Peter, 2026-10-03; research 01, Vectors and exact signs)."""

import math
from decimal import Decimal, localcontext

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

import geometry2d_oracles as oracle
from splintercam import _kernels

# Full-precision coordinates within the predicates' input range (a precondition).
coordinate = st.floats(-1000.0, 1000.0).filter(lambda v: v == 0.0 or abs(v) >= 1e-30)
point = st.tuples(coordinate, coordinate)


def _ray_end_height(
    centre: tuple[float, float], p0: tuple[float, float], toward: tuple[float, float]
) -> float:
    with localcontext() as ctx:
        ctx.prec = 60
        cx, cy, px, py, tx, ty = (Decimal(v) for v in (*centre, *p0, *toward))
        r = ((px - cx) ** 2 + (py - cy) ** 2).sqrt()
        return float(cy + r * (ty - cy) / ((tx - cx) ** 2 + (ty - cy) ** 2).sqrt())


@pytest.mark.req("REQ-G2D-135", "REQ-G2D-005")
@given(centre=point, p0=point, toward=point, offset=st.sampled_from([-1, 0, 1]))
def test_ray_height_sign_matches_exact_rationals(
    centre: tuple[float, float],
    p0: tuple[float, float],
    toward: tuple[float, float],
    offset: int,
) -> None:
    assume(p0 != centre and toward != centre)
    q_y = _ray_end_height(centre, p0, toward)
    if offset:
        q_y = math.nextafter(q_y, offset * math.inf)
    assume(q_y == 0.0 or abs(q_y) >= 1e-30)
    expected = oracle.ray_height_sign(q_y, centre, p0, toward)
    assert _kernels.geometry2d.ray_height_sign(q_y, centre, p0, toward) == expected
