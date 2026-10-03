# SPDX-License-Identifier: Apache-2.0
"""The circle through three points (research 01, Circle through three points; SRC-032, p. 359)."""

from dataclasses import dataclass

import numpy as np

from splintercam import _kernels
from splintercam.foundation import Context

from ._curves import Point
from ._predicates import point_rows


@dataclass(frozen=True, slots=True)
class Circle:
    """A circle: its centre and its radius in mm."""

    centre: Point
    radius_mm: float


def circle_through(p1: Point, p2: Point, p3: Point, ctx: Context) -> Circle | None:
    """The circle through three points, or None when they are collinear, P2 lies within eps_len
    of the line P1P3 or P1 = P3. The radius is |P1 - C| (ours); no radius limit of its own.

    Implements: REQ-G2D-097 to 101.
    """
    a, b, c = point_rows([p1], [p2], [p3])
    centres, radii = np.zeros((1, 2)), np.zeros(1)
    found = np.zeros(1, dtype=np.int8)
    _kernels.geometry2d.circles_through(
        a, b, c, ctx.tolerances.length_eps_mm, centres, radii, found
    )
    if found[0] == 0:
        return None
    return Circle((float(centres[0, 0]), float(centres[0, 1])), float(radii[0]))
