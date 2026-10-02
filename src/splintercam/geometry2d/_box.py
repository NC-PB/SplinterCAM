# SPDX-License-Identifier: Apache-2.0
"""Bounding boxes of lines and arcs (research 01, Helpers)."""

import math
from dataclasses import dataclass

from splintercam.foundation import Context

from ._curves import Arc, Curve, Point


@dataclass(frozen=True, slots=True)
class Box:
    """An axis-aligned box in mm."""

    x_min_mm: float
    y_min_mm: float
    x_max_mm: float
    y_max_mm: float


def _octant(point: Point, centre: Point, mirrored: bool) -> int:
    # The direction of point - C by exact comparisons of doubles (REQ-G2D-005): 0 on the +x
    # axis, then counter-clockwise, odd inside a quadrant and even on an axis (ours). Mirrored
    # in y for a clockwise arc, so the sweep runs counter-clockwise.
    sx = (point[0] > centre[0]) - (point[0] < centre[0])
    sy = (point[1] > centre[1]) - (point[1] < centre[1])
    if mirrored:
        sy = -sy
    return {(1, 0): 0, (1, 1): 1, (0, 1): 2, (-1, 1): 3, (-1, 0): 4, (-1, -1): 5, (0, -1): 6}.get(
        (sx, sy), 7
    )


def _axes_in_sweep(arc: Arc) -> list[int]:
    """The axis directions (0, 1, 2, 3 for 0, π/2, π, 3π/2) the arc passes, decided exactly."""
    if abs(arc.sweep_rad) == math.tau:
        return [0, 1, 2, 3]
    mirrored = arc.sweep_rad < 0.0
    start = _octant(arc.p0, arc.centre, mirrored)
    end = _octant(arc.p1, arc.centre, mirrored)
    if start == end:  # both ends in one octant: the sweep is tiny or nearly a full turn
        return [0, 1, 2, 3] if abs(arc.sweep_rad) > math.pi else []
    reach = (end - start) % 8
    # REQ-G2D-043 lets P1 lie up to eps_len / r past either side of where the sweep ends, so its
    # octant can contradict the sweep near 0 and near a full turn: the sweep governs (ours).
    if abs(arc.sweep_rad) < math.pi / 2 and reach >= 4:
        return []
    if abs(arc.sweep_rad) > 3 * math.pi / 2 and reach <= 4:
        return [0, 1, 2, 3]
    passed = [axis for axis in range(4) if (2 * axis - start) % 8 <= reach]
    # Back from the mirrored frame: the axis at angle a is the one at -a.
    return sorted((4 - axis) % 4 for axis in passed) if mirrored else passed


def bounding_box(curve: Curve, ctx: Context) -> Box:
    """The box of a line's end points, or of an arc's end points and the points at 0, π/2, π
    and 3π/2 about its centre that lie in its sweep.

    Implements: REQ-G2D-213, REQ-G2D-214.
    """
    del ctx  # every public function takes the Context (SPEC, Public interface)
    points = [curve.p0, curve.p1]
    if isinstance(curve, Arc):
        (cx, cy), r = curve.centre, curve.radius_mm
        extremes = [(cx + r, cy), (cx, cy + r), (cx - r, cy), (cx, cy - r)]
        points += [extremes[axis] for axis in _axes_in_sweep(curve)]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return Box(min(xs), min(ys), max(xs), max(ys))
