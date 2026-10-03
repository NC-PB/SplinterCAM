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
    return sign(twice_area(a, b, c))


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


def circumcentre(p1: P, p2: P, p3: P) -> tuple[Fraction, Fraction]:
    """The exact centre of the circle through three non-collinear points (SRC-032, p. 359)."""
    x1, y1, x2, y2, x3, y3 = (Fraction(v) for v in (*p1, *p2, *p3))
    ux, uy, vx, vy = x1 - x3, y1 - y3, x2 - x3, y2 - y3
    d = ux * vy - uy * vx
    u2, v2 = ux * ux + uy * uy, vx * vx + vy * vy
    return x3 - (uy * v2 - vy * u2) / (2 * d), y3 + (ux * v2 - vx * u2) / (2 * d)


def line_foot(q: P, p0: P, p1: P) -> tuple[Fraction, Fraction, Fraction]:
    """t and the foot of the clamped perpendicular from q onto the segment p0p1, exactly."""
    qx, qy, ax, ay, bx, by = (Fraction(v) for v in (*q, *p0, *p1))
    dx, dy = bx - ax, by - ay
    t = min(max(((qx - ax) * dx + (qy - ay) * dy) / (dx * dx + dy * dy), Fraction(0)), Fraction(1))
    return t, ax + t * dx, ay + t * dy


def twice_area(a: P, b: P, c: P) -> Fraction:
    """orient2d(a, b, c) as an exact value: twice the signed area of the triangle."""
    ax, ay, bx, by, cx, cy = (Fraction(v) for v in (*a, *b, *c))
    return (ax - cx) * (by - cy) - (ay - cy) * (bx - cx)


def polygon_area(points: list[P]) -> Fraction:
    """The exact signed area of the closed polygon through `points` (shoelace formula)."""
    total = Fraction(0)
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        total += Fraction(x0) * Fraction(y1) - Fraction(x1) * Fraction(y0)
    return total / 2


def phi_minus_sin(phi: float) -> Fraction:
    """φ - sin φ by its series φ³/3! - φ⁵/5! + …: 40 terms leave less than (2π)^83 / 83! < 1e-58
    for |φ| <= 2π."""
    x, total, term = Fraction(phi), Fraction(0), Fraction(phi)
    for k in range(1, 41):
        term = term * x * x / ((2 * k) * (2 * k + 1))
        total += term if k % 2 == 1 else -term
    return total


def loop_area(rows: list[list[float]]) -> Fraction:
    """The signed area of research 01 for one loop of curve rows [x0, y0, x1, y1, cx, cy, sweep]:
    the polygon of the end points plus r²(φ - sin φ)/2 per arc with r = |P0 - C|, exact but for
    the truncation of `phi_minus_sin`."""
    total = polygon_area([(row[0], row[1]) for row in rows])
    for x0, y0, _, _, cx, cy, sweep in rows:
        if sweep != 0.0:
            total += squared_distance((x0, y0), (cx, cy)) * phi_minus_sin(sweep) / 2
    return total


def winding(q: P, points: list[P]) -> int | None:
    """The winding number of the closed polygon through `points` about q by a ray to the right,
    with half-open height ranges, exactly; None when q lies on an edge."""
    total = 0
    for a, b in zip(points, points[1:] + points[:1], strict=True):
        side = orient2d(a, b, q)
        within = min(a[0], b[0]) <= q[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= q[1] <= max(
            a[1], b[1]
        )
        if side == 0 and within:
            return None
        if a[1] <= q[1] < b[1] and side > 0:
            total += 1
        elif b[1] <= q[1] < a[1] and side < 0:
            total -= 1
    return total


def ray_height_sign(q_y: float, centre: P, p0: P, toward: P) -> int:
    """The sign of q_y minus the height where the ray from `centre` through `toward` meets the
    circle about `centre` through `p0`, exactly: by sides of c_y, then by squares."""
    qy, cx, cy, px, py, tx, ty = (Fraction(v) for v in (q_y, *centre, *p0, *toward))
    q_side, ray_side = sign(qy - cy), sign(ty - cy)
    if q_side != ray_side:
        return 1 if q_side > ray_side else -1
    if q_side == 0:
        return 0
    left = (qy - cy) ** 2 * ((tx - cx) ** 2 + (ty - cy) ** 2)
    right = ((px - cx) ** 2 + (py - cy) ** 2) * (ty - cy) ** 2
    return q_side * sign(left - right)
