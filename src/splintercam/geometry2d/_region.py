# SPDX-License-Identifier: Apache-2.0
"""Point in region (research 01, Point in region): the exact layer."""

from enum import IntEnum

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam import _kernels

from ._predicates import point_rows
from ._rows import CurveRows


class PointLocation(IntEnum):
    """Where a point lies against a region."""

    OUT = 0
    IN = 1
    ON = 2


def point_in_region_exact(q: ArrayLike, loops: CurveRows) -> NDArray[np.int8]:
    """The exact layer: per point of q ((n, 2)) its `PointLocation` against all loops, ON only on
    the boundary itself, else IN where the winding number is not 0 (internal, for tests).

    Implements: REQ-G2D-135, REQ-G2D-139, REQ-G2D-143, REQ-G2D-145.
    """
    (points,) = point_rows(q)
    out = np.empty(points.shape[0], dtype=np.int8)
    _kernels.geometry2d.point_locations(points, loops.rows, out)
    out.flags.writeable = False
    return out
