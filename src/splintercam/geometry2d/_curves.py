# SPDX-License-Identifier: Apache-2.0
"""Lines and arcs: the curve type of slice 1, the arc form and its validation (research 01,
Curves; D-057)."""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context, Diagnostic, Result, Severity

type Point = tuple[float, float]
"""A point or vector in the plane, in mm."""


@dataclass(frozen=True, slots=True)
class Line:
    """The segment from `p0` to `p1`. Build it with `make_line` to have it checked."""

    p0: Point
    p1: Point


@dataclass(frozen=True, slots=True)
class Arc:
    """A circular arc in centre form (D-057): its end points exactly, its centre and a signed
    sweep in radians, positive CCW, 0 < |sweep| <= 2π. P0 defines the radius; P1 is never moved.
    A full circle has P0 = P1 and sweep ±2π. Build it with `make_arc` to have it checked.
    """

    p0: Point
    p1: Point
    centre: Point
    sweep_rad: float

    @property
    def radius_mm(self) -> float:
        """r = |P0 - C| (REQ-G2D-038)."""
        return distance(self.p0, self.centre)


type Curve = Line | Arc
"""One curve of a chain (REQ-G2D-035)."""


def distance(a: Point, b: Point) -> float:
    # sqrt of a sum of squares: correctly rounded operations only, the same on every platform.
    dx, dy = a[0] - b[0], a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


def _curve_invalid(message: str) -> Diagnostic:
    return Diagnostic("CURVE_INVALID", Severity.ERROR, message)


def _point(values: Point) -> Point:
    return (float(values[0]), float(values[1]))


def make_line(p0: Point, p1: Point, ctx: Context) -> Result[Line]:
    """The line from `p0` to `p1`, or `CURVE_INVALID` for a NaN or infinite value (REQ-G2D-040).

    Implements: REQ-G2D-040.
    """
    del ctx  # every public function takes the Context (SPEC, Public interface)
    line = Line(_point(p0), _point(p1))
    if not all(math.isfinite(value) for value in (*line.p0, *line.p1)):
        return Result(None, (_curve_invalid(f"line with a non-finite value: {line}"),))
    return Result(line)


def make_arc(
    p0: Point, p1: Point, centre: Point, sweep_rad: float, ctx: Context
) -> Result[tuple[Curve, ...]]:
    """The arc from `p0` to `p1` about `centre`, checked in the order of the SPEC.

    Returns `(Arc,)`; `(Line,)` when r <= eps_len, P0 != P1 and P1 lies within eps_len of the
    circle; `()` when r <= eps_len and P0 = P1; a full circle for a nearly closed arc. Errors:
    `CURVE_INVALID` for a non-finite value or a sweep of 0 or beyond ±2π, `ARC_INCONSISTENT` when
    P1 is off the circle or the sweep does not fit the end points.

    Implements: REQ-G2D-037 to 045, REQ-G2D-047 to 049.
    """
    arc = Arc(_point(p0), _point(p1), _point(centre), float(sweep_rad))
    if not all(math.isfinite(v) for v in (*arc.p0, *arc.p1, *arc.centre, arc.sweep_rad)):
        return Result(None, (_curve_invalid(f"arc with a non-finite value: {arc}"),))
    if arc.sweep_rad == 0.0 or abs(arc.sweep_rad) > math.tau:
        return Result(None, (_curve_invalid(f"arc sweep must lie in (0, 2π]: {arc}"),))
    eps = ctx.tolerances.length_eps_mm
    radius = arc.radius_mm
    if radius <= eps:
        return _tiny_arc(arc, radius, eps)
    size = abs(arc.sweep_rad)
    if distance(arc.p0, arc.p1) <= eps and size > math.pi and (math.tau - size) * radius <= eps:
        return Result((Arc(arc.p0, arc.p0, arc.centre, math.copysign(math.tau, arc.sweep_rad)),))
    message = arc_inconsistency(np.array([[*arc.p0, *arc.p1, *arc.centre, arc.sweep_rad]]), eps)
    if message is not None:
        return Result(None, (Diagnostic("ARC_INCONSISTENT", Severity.ERROR, f"{message}: {arc}"),))
    return Result((arc,))


def _tiny_arc(arc: Arc, radius: float, eps: float) -> Result[tuple[Curve, ...]]:
    """An arc with r <= eps_len: its chord, nothing when closed, or `ARC_INCONSISTENT` when P1
    lies off the circle. The radial check comes first, so P1 far from a tiny circle gives no long
    line (DEC-G2D-018)."""
    if abs(distance(arc.p1, arc.centre) - radius) > eps:
        message = f"P1 is off the arc's circle: {arc}"
        return Result(None, (Diagnostic("ARC_INCONSISTENT", Severity.ERROR, message),))
    return Result(() if arc.p0 == arc.p1 else (Line(arc.p0, arc.p1),))


_ARC_CHECK_MESSAGES = {1: "P1 is off the arc's circle", 2: "the sweep does not fit the end points"}


def arc_inconsistency(rows: NDArray[np.float64], length_eps_mm: float) -> str | None:
    """The first arc rule `rows` (C-contiguous (m, 7) float64 curve rows) break, or None."""
    checks = np.empty(rows.shape[0], dtype=np.int8)
    _kernels.geometry2d.check_arcs(rows, length_eps_mm, checks)
    broken = np.flatnonzero(checks)
    if broken.size == 0:
        return None
    first = int(broken[0])
    return f"row {first}: {_ARC_CHECK_MESSAGES[int(checks[first])]}"
