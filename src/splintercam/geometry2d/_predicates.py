# SPDX-License-Identifier: Apache-2.0
"""Direction tests (research 01, Tolerances); the exact predicates follow in plan 0003, step 5."""

import math

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam.foundation import Context


def are_parallel(a: ArrayLike, b: ArrayLike, ctx: Context) -> NDArray[np.bool_]:
    """For rows of directions a and b ((n, 2) each), whether they are parallel: the square of their
    cross product is at most sin²(eps_ang)·|a|²·|b|² (research 01, Tolerances).

    Opposite directions and a zero vector count as parallel (REQ-G2D-027).

    Implements: REQ-G2D-027.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    cross = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    limit = math.sin(ctx.tolerances.angle_eps_rad) ** 2
    return cross * cross <= limit * np.sum(a * a, axis=1) * np.sum(b * b, axis=1)
