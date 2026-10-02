# SPDX-License-Identifier: Apache-2.0
"""DXF bulges: arcs from bulges at import and bulges from arcs at export (research 01, Curves;
D-057; SRC-123 for the bulge's meaning, the formulas ours)."""

import math

from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._curves import Arc, Curve, Line, Point, distance, make_arc


def arc_from_bulge(p0: Point, p1: Point, bulge: float, ctx: Context) -> Result[Curve]:
    """The arc from `p0` to `p1` with the DXF bulge b = tan(φ/4), centre on the bisector.

    A line for b = 0 or a sagitta c·|b|/2 within eps_len (ours); `CURVE_INVALID` for a non-finite
    value or a bulge on a zero chord. The arc then passes `make_arc`.

    Implements: REQ-G2D-044, REQ-G2D-050, REQ-G2D-051.
    """
    if not all(math.isfinite(value) for value in (*p0, *p1, bulge)):
        message = f"bulge conversion with a non-finite value: {p0}, {p1}, {bulge}"
        return Result(None, (Diagnostic("CURVE_INVALID", Severity.ERROR, message),))
    chord = distance(p0, p1)
    if chord == 0.0 and bulge != 0.0:
        message = f"bulge {bulge} on a zero chord at {p0}"
        return Result(None, (Diagnostic("CURVE_INVALID", Severity.ERROR, message),))
    if chord * abs(bulge) / 2 <= ctx.tolerances.length_eps_mm:
        return Result(Line(p0, p1))
    # C = M + d·n_left, d = c(1 - b²)/(4b), n_left the unit normal left of P0 -> P1.
    scale = (1.0 - bulge * bulge) / (4.0 * bulge)  # d / c
    centre = (
        (p0[0] + p1[0]) / 2 - scale * (p1[1] - p0[1]),
        (p0[1] + p1[1]) / 2 + scale * (p1[0] - p0[0]),
    )
    built = make_arc(p0, p1, centre, 4.0 * math.atan(bulge), ctx)
    if built.value is None:
        return Result(None, built.diagnostics)
    return Result(built.value[0], built.diagnostics)


def bulges_from_arc(arc: Arc, ctx: Context) -> tuple[tuple[Arc, float], ...]:
    """The arc with its bulge tan(φ/4); a full circle as two halves split at the angle φ/2, the
    point opposite P0, each with the bulge ±1 (ours).

    Implements: REQ-G2D-052, REQ-G2D-053.
    """
    del ctx  # every public function takes the Context (SPEC, Public interface)
    if arc.p0 != arc.p1:
        return ((arc, math.tan(arc.sweep_rad / 4)),)
    cx, cy = arc.centre
    opposite = (cx - (arc.p0[0] - cx), cy - (arc.p0[1] - cy))
    half = arc.sweep_rad / 2
    bulge = math.copysign(1.0, half)
    return (
        (Arc(arc.p0, opposite, arc.centre, half), bulge),
        (Arc(opposite, arc.p0, arc.centre, half), bulge),
    )
