# SPDX-License-Identifier: Apache-2.0
"""Point in region (research 01, Point in region): an exact layer and a tolerance layer."""

from enum import IntEnum

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam import _kernels
from splintercam.foundation import Context

from ._predicates import point_rows
from ._rows import CurveRows


class PointLocation(IntEnum):
    """Where a point lies against a region."""

    OUT = 0
    IN = 1
    ON = 2


def _locations(q: ArrayLike, loops: CurveRows, length_eps_mm: float) -> NDArray[np.int8]:
    (points,) = point_rows(q)
    out = np.empty(points.shape[0], dtype=np.int8)
    _kernels.geometry2d.point_locations(points, loops.rows, length_eps_mm, out)  # 0: exact only
    out.flags.writeable = False
    return out


def point_in_region(q: ArrayLike, loops: CurveRows, ctx: Context) -> NDArray[np.int8]:
    """Per point of q ((n, 2)) its `PointLocation` against all loops: ON on the boundary or within
    eps_len of it, else IN where the winding number is not 0 and OUT where it is 0.

    Implements: REQ-G2D-134, REQ-G2D-148 to 150.
    """
    return _locations(q, loops, ctx.tolerances.length_eps_mm)


def point_in_region_exact(q: ArrayLike, loops: CurveRows) -> NDArray[np.int8]:
    """The exact layer alone: ON only on the boundary itself (internal, for tests).

    Implements: REQ-G2D-135, REQ-G2D-139, REQ-G2D-143, REQ-G2D-145.
    """
    return _locations(q, loops, 0.0)
