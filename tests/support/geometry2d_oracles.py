# SPDX-License-Identifier: Apache-2.0
"""Exact-rational oracles for the geometry2d predicates (research 01, Vectors and exact signs)."""

from fractions import Fraction

type P = tuple[float, float]

# SRC-032, p. 308: the predicates are exact while every nonzero input has an exponent in
# [-142, 201]; below that, products underflow (geometry2d SPEC, precondition of the predicates).
SAFE_MIN = 2.0**-142
SAFE_MAX = 2.0**201


def in_safe_range(*values: float) -> bool:
    """Whether every value is 0 or has a magnitude in [2^-142, 2^201]."""
    return all(v == 0.0 or SAFE_MIN <= abs(v) <= SAFE_MAX for v in values)


def sign(value: Fraction) -> int:
    return (value > 0) - (value < 0)


def orient2d(a: P, b: P, c: P) -> int:
    ax, ay, bx, by, cx, cy = (Fraction(v) for v in (*a, *b, *c))
    return sign((ax - cx) * (by - cy) - (ay - cy) * (bx - cx))


def incircle(a: P, b: P, c: P, d: P) -> int:
    rows: list[tuple[Fraction, Fraction, Fraction]] = []
    for p in (a, b, c):
        dx, dy = Fraction(p[0]) - Fraction(d[0]), Fraction(p[1]) - Fraction(d[1])
        rows.append((dx, dy, dx * dx + dy * dy))
    (a0, a1, a2), (b0, b1, b2), (c0, c1, c2) = rows
    det = a0 * (b1 * c2 - b2 * c1) - a1 * (b0 * c2 - b2 * c0) + a2 * (b0 * c1 - b1 * c0)
    return sign(det)


def squared_distance(p: P, q: P) -> Fraction:
    dx, dy = Fraction(p[0]) - Fraction(q[0]), Fraction(p[1]) - Fraction(q[1])
    return dx * dx + dy * dy


def in_arc_circle(q: P, centre: P, p0: P) -> int:
    """+1 inside the circle about `centre` through `p0`, 0 on it, -1 outside (REQ-G2D-022)."""
    return sign(squared_distance(p0, centre) - squared_distance(q, centre))
