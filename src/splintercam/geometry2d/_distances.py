# SPDX-License-Identifier: Apache-2.0
"""Closest points on lines and arcs (research 01, Distances and closest points)."""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context

from ._curves import Arc, Curve, Line, Point, distance
from ._predicates import in_arc_circle, orient2d, point_rows


@dataclass(frozen=True, slots=True)
class ClosestPoint:
    """The point of a curve nearest to a query point: t in [0, 1] on a line, the angle from P0
    in the sense of the sweep on an arc (ours), and the distance in mm."""

    point: Point
    parameter: float
    distance_mm: float


# 0 when the direction of q - C lies in [0, π) counter-clockwise from that of start - C, 1 in
# [π, 2π), decided by exact signs (REQ-G2D-005); q and start differ from C.
def _half(start: Point, centre: Point, q: Point) -> int:
    cross = int(orient2d([centre], [start], [q])[0])
    if cross != 0:
        return 0 if cross > 0 else 1
    # Parallel directions: the same one when a nonzero coordinate difference has the same sign.
    axis = 0 if start[0] != centre[0] else 1
    return 0 if (q[axis] > centre[axis]) == (start[axis] > centre[axis]) else 1


def _in_sweep(arc: Arc, q: Point) -> bool:
    sweep = abs(arc.sweep_rad)
    # A clockwise arc covers the directions of the counter-clockwise arc from P1 to P0.
    start, end = (arc.p0, arc.p1) if arc.sweep_rad > 0.0 else (arc.p1, arc.p0)
    centre = arc.centre
    end_half = _half(start, centre, end)
    # REQ-G2D-043 lets P1 lie up to eps_len / r past where the sweep ends, so its direction can
    # contradict the sweep near 0 and near a full turn: the sweep governs (ours, as bounding_box).
    # Sound while eps_len / r < 1 rad, which make_arc ensures (r > eps_len); a full circle has
    # P1 = P0, so its end lies in half 0.
    if sweep < math.pi / 2 and end_half == 1:
        return False
    if sweep > 3 * math.pi / 2 and end_half == 0:
        return True
    q_half = _half(start, centre, q)
    if q_half != end_half:
        return q_half < end_half
    return orient2d([centre], [q], [end])[0] >= 0  # within one half: q not after the end


def _arc_parameter(arc: Arc, q: Point) -> float:
    (cx, cy), (px, py) = arc.centre, arc.p0
    ax, ay, bx, by = px - cx, py - cy, q[0] - cx, q[1] - cy
    angle = math.atan2(math.copysign(1.0, arc.sweep_rad) * (ax * by - ay * bx), ax * bx + ay * by)
    if angle < 0.0:
        angle += math.tau
    angle += 0.0  # -0.0 on P0's ray of a clockwise arc becomes +0.0
    sweep = abs(arc.sweep_rad)
    if angle > sweep:  # rounding just outside: the nearer end of the sweep
        angle = sweep if angle - sweep < math.tau - angle else 0.0
    return angle


def _closest_on_line(line: Line, q: Point) -> ClosestPoint:
    (x0, y0), (x1, y1) = line.p0, line.p1
    dx, dy = x1 - x0, y1 - y0
    length2 = dx * dx + dy * dy
    if length2 == 0.0:
        return ClosestPoint(line.p0, 0.0, distance(q, line.p0))
    t = min(max(((q[0] - x0) * dx + (q[1] - y0) * dy) / length2, 0.0), 1.0)
    point = line.p0 if t == 0.0 else line.p1 if t == 1.0 else (x0 + t * dx, y0 + t * dy)
    return ClosestPoint(point, t, distance(q, point))


def _closest_on_arc(arc: Arc, q: Point) -> ClosestPoint:
    centre, r = arc.centre, arc.radius_mm
    if q == centre:
        return ClosestPoint(arc.p0, 0.0, r)
    if _in_sweep(arc, q):
        d = distance(q, centre)
        point = (centre[0] + r * (q[0] - centre[0]) / d, centre[1] + r * (q[1] - centre[1]) / d)
        return ClosestPoint(point, _arc_parameter(arc, q), abs(d - r))
    # P1 strictly nearer: inside the circle about q through P0, an exact sign (REQ-G2D-005).
    if in_arc_circle([arc.p1], [q], [arc.p0])[0] > 0:
        return ClosestPoint(arc.p1, abs(arc.sweep_rad), distance(q, arc.p1))
    return ClosestPoint(arc.p0, 0.0, distance(q, arc.p0))


def closest_point(curve: Curve, q: Point, ctx: Context) -> ClosestPoint:
    """The point of a line or arc nearest to q (research 01, Distances and closest points).

    Implements: REQ-G2D-091 to 094, REQ-G2D-096.
    """
    del ctx  # every public function takes the Context (SPEC, Public interface)
    q = (float(q[0]), float(q[1]))
    if not (math.isfinite(q[0]) and math.isfinite(q[1])):
        raise ValueError(f"the query point must be finite, got {q}")
    return _closest_on_arc(curve, q) if isinstance(curve, Arc) else _closest_on_line(curve, q)


def polyline_distances(
    q: NDArray[np.float64],
    points: NDArray[np.float64],
    loop_starts: NDArray[np.int64],
    limit_mm: float,
) -> NDArray[np.float64]:
    """Capped distances to closed polylines (SPEC, Public interface, internal entries; DEC-G2D-013;
    research 01, Loop tree, rules 3 and 5). Broken input is a `ValueError`, raised here so the
    kernel's own checks stay a backstop (REQ-G2D-239)."""
    (query,) = point_rows(q)
    out = np.empty(query.shape[0], dtype=np.float64)
    vertices = np.ascontiguousarray(points, dtype=np.float64)
    starts = np.ascontiguousarray(loop_starts, dtype=np.int64)
    if not (math.isfinite(limit_mm) and limit_mm > 0.0):
        raise ValueError(f"limit must be finite and > 0, got {limit_mm!r}")
    if not np.isfinite(vertices).all():
        raise ValueError("every polyline vertex must be finite")
    ends = np.append(starts[1:], vertices.shape[0])
    if starts.size == 0 and vertices.size > 0:
        raise ValueError("loop_starts must name the loops of the points")
    if starts.size > 0 and (starts[0] != 0 or np.any(ends <= starts)):
        raise ValueError(
            f"loop_starts must start at 0 and ascend strictly below the point count: {starts}"
        )
    _kernels.geometry2d.polyline_distances(query, vertices, starts, limit_mm, out)
    out.flags.writeable = False
    return out
