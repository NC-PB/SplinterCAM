# SPDX-License-Identifier: Apache-2.0
"""Closest points on lines and arcs (research 01, Distances and closest points)."""

import math
from dataclasses import dataclass

from splintercam.foundation import Context

from ._curves import Arc, Curve, Line, Point
from ._predicates import orient2d


@dataclass(frozen=True, slots=True)
class ClosestPoint:
    """The point of a curve nearest to a query point: t in [0, 1] on a line, the angle from P0
    in the sense of the sweep on an arc (ours), and the distance in mm."""

    point: Point
    parameter: float
    distance_mm: float


def _sign(a: float, b: float) -> int:
    return (a > b) - (a < b)


def _half(start: Point, centre: Point, q: Point) -> int:
    """0 when the direction of q - C lies in [0, π) counter-clockwise from that of start - C,
    1 in [π, 2π), decided by exact signs (REQ-G2D-005)."""
    cross = int(orient2d([centre], [start], [q])[0])
    if cross != 0:
        return 0 if cross > 0 else 1
    # Parallel directions: the same one when a nonzero coordinate difference has the same sign.
    axis = 0 if start[0] != centre[0] else 1
    return 0 if _sign(q[axis], centre[axis]) == _sign(start[axis], centre[axis]) else 1


def _in_sweep(arc: Arc, q: Point) -> bool:
    """Whether the direction of q - C lies in the arc's sweep, by exact signs (REQ-G2D-093)."""
    sweep = abs(arc.sweep_rad)
    if sweep == math.tau:
        return True
    # A clockwise arc covers the directions of the counter-clockwise arc from P1 to P0.
    start, end = (arc.p0, arc.p1) if arc.sweep_rad > 0.0 else (arc.p1, arc.p0)
    centre = arc.centre
    end_half = _half(start, centre, end)
    # REQ-G2D-043 lets P1 lie up to eps_len / r past where the sweep ends, so its direction can
    # contradict the sweep near 0 and near a full turn: the sweep governs (ours, as bounding_box).
    if sweep < math.pi / 2 and end_half == 1:
        return False
    if sweep > 3 * math.pi / 2 and end_half == 0:
        return True
    q_half = _half(start, centre, q)
    if q_half != end_half:
        return q_half < end_half
    return orient2d([centre], [q], [end])[0] >= 0  # within one half: q not after the end


def _arc_parameter(arc: Arc, q: Point) -> float:
    """The angle from P0 to the direction of q - C in the sense of the sweep, in [0, |sweep|]."""
    (cx, cy), (px, py) = arc.centre, arc.p0
    ax, ay, bx, by = px - cx, py - cy, q[0] - cx, q[1] - cy
    angle = math.atan2(math.copysign(1.0, arc.sweep_rad) * (ax * by - ay * bx), ax * bx + ay * by)
    if angle < 0.0:
        angle += math.tau
    sweep = abs(arc.sweep_rad)
    if angle > sweep:  # rounding just outside: the nearer end of the sweep
        angle = sweep if angle - sweep < math.tau - angle else 0.0
    return angle


def _closest_on_line(line: Line, q: Point) -> ClosestPoint:
    (x0, y0), (x1, y1) = line.p0, line.p1
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy
    if length2 == 0.0:
        return ClosestPoint(line.p0, 0.0, math.dist(q, line.p0))
    t = min(max(((q[0] - x0) * dx + (q[1] - y0) * dy) / length2, 0.0), 1.0)
    point = line.p0 if t == 0.0 else line.p1 if t == 1.0 else (x0 + t * dx, y0 + t * dy)
    return ClosestPoint(point, t, math.dist(q, point))


def _closest_on_arc(arc: Arc, q: Point) -> ClosestPoint:
    centre, r = arc.centre, arc.radius_mm
    if q == centre:
        return ClosestPoint(arc.p0, 0.0, r)
    if _in_sweep(arc, q):
        d = math.dist(q, centre)
        point = (centre[0] + r * (q[0] - centre[0]) / d, centre[1] + r * (q[1] - centre[1]) / d)
        return ClosestPoint(point, _arc_parameter(arc, q), abs(d - r))
    d0, d1 = math.dist(q, arc.p0), math.dist(q, arc.p1)
    if d1 < d0:
        return ClosestPoint(arc.p1, abs(arc.sweep_rad), d1)
    return ClosestPoint(arc.p0, 0.0, d0)


def closest_point(curve: Curve, q: Point, ctx: Context) -> ClosestPoint:
    """The point of a line or arc nearest to q (research 01, Distances and closest points).

    Implements: REQ-G2D-091 to 094, REQ-G2D-096.
    """
    del ctx  # every public function takes the Context (SPEC, Public interface)
    q = (float(q[0]), float(q[1]))
    return _closest_on_arc(curve, q) if isinstance(curve, Arc) else _closest_on_line(curve, q)
