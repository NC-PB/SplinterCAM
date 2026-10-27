# SPDX-License-Identifier: Apache-2.0
"""The depth passes and their moves in the plane (research 22, Method 3 and 6): equal steps from
z_top to z_bottom; per pass P → S, the loop, S → P as LINE rows."""

import math

import numpy as np
from numpy.typing import NDArray

from splintercam.cl import Role
from splintercam.toolpath import LevelPass

CUT_CLASS, PLUNGE_CLASS = 0, 1  # the header's feed classes, in REQ-PRF-018's order


def _pass_count(depth: float, step: float, eps: float) -> int:
    # DEC-PRF-004: a quotient one ulp over an integer gives no extra pass; never 0.
    n = math.ceil(depth / step)
    return n - 1 if n > 1 and (n - 1) * step >= depth - eps else n


def first_level(top: float, bottom: float, step: float, eps: float) -> float:
    """z_1 of `levels`, without building the others (REQ-PRF-005)."""
    n = _pass_count(top - bottom, step, eps)
    return bottom if n == 1 else top - (top - bottom) / n


def levels(top: float, bottom: float, step: float, eps: float) -> list[float]:
    """z_i = z_top - i·Δ, i = 1 … n, of equal depth Δ, the last z_bottom exactly (REQ-PRF-016)."""
    n = _pass_count(top - bottom, step, eps)
    delta = (top - bottom) / n
    return [top - i * delta for i in range(1, n)] + [bottom]


def level_passes(
    loop: NDArray[np.float64], approach: tuple[float, float], zs: list[float]
) -> tuple[LevelPass, ...]:
    """One pass per level: WHERE P is not S, P → S at the plunge feed (APPROACH) and S → P at the
    cutting feed (RETRACT) round the CW loop from S to S (REQ-PRF-017; research 22, trap 1)."""
    apart = (loop[0, 0], loop[0, 1]) != approach  # DEC-PRF-007 (3): the points, not d > 0
    p = np.array([approach], dtype=np.float64)
    points = np.concatenate([p, loop, p]) if apart else loop
    m = points.shape[0] - 1
    role = np.full(m, Role.CUT, dtype=np.int8)
    if apart:
        role[0], role[-1] = Role.APPROACH, Role.RETRACT
    rows = np.column_stack([points[:-1], points[1:], np.full((m, 2), np.nan), np.zeros(m)])
    feed = np.where(role == Role.APPROACH, PLUNGE_CLASS, CUT_CLASS).astype(np.int64)
    for array in (rows, role, feed):
        array.flags.writeable = False
    return tuple(LevelPass(z, rows, role, feed) for z in zs)
