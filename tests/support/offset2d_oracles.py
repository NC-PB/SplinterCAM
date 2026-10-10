# SPDX-License-Identifier: Apache-2.0
"""Oracles for offset2d's tests, independent of geometry2d's kernels and of Clipper2 (A-053):
the distance from points to loops of true lines and arcs, "inside R" by a winding test on the true
curves, offset and Boolean membership by research 02's definitions, a seeded sampler that keeps
points out of a band, and the bands of the offset2d SPEC (Requirements, preamble).

Loops are geometry2d's `CurveRows`: rows [x0, y0, x1, y1, cx, cy, sweep] in mm and radians, a line
where the sweep is 0. An arc runs on the circle of radius r = |P0 - C| from P0, in the direction
of its sweep, to the ray from C through P1, then along that ray to P1 (geometry2d's radial
connector, REQ-G2D-135; of length 0 where P1 lies on the circle). Its turn is the angle from P0 to
that ray in the sweep's direction, taken within π of |sweep|, so a sweep of ±2π with P1 = P0 is a
full circle. The oracles take rows as geometry2d's `curve_rows` accepts them; rows whose P1 lies
behind P0 (a turn below 0) are outside their contract.

Accuracy. Everything runs in float64 with vectorised NumPy. Let S be the largest absolute
coordinate of the points, row ends and centres plus the largest radius, and ε = 2^-53. Then
`distance_to_curves` is within 64·ε·S of the exact distance to the true curves (below 1.5e-10 mm
for S <= 10^4 mm, six orders below the grid unit u = 1e-4 mm); the property tests check it against
exact rationals. `inside_region` is exact at every point farther than 64·ε·S from the curves: the
chord polygon and the circular segments share one orientation expression per chord, and a point
on a chord's line is decided as Sunday's crossing rule decides it, as if moved by (+δx, +δy) with
δy << δx. Points within the SPEC's bands are never that close, so the oracles add nothing to a
band.
"""

import math
from dataclasses import dataclass
from typing import Literal, NamedTuple

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam.foundation import TOLERANCE_DEFAULTS, ToleranceSet
from splintercam.geometry2d import CurveRows, RegionKind

type Points = NDArray[np.float64]
type Mask = NDArray[np.bool_]
type BoxMM = tuple[float, float, float, float]  # x0, y0, x1, y1
type BooleanName = Literal["UNION", "DIFFERENCE", "INTERSECTION"]  # offset2d's BooleanOp names

# Points per block: bounds the (points x rows) arrays to a few MB. Not a tolerance.
_CHUNK = 4096
# The sampler gives up after this many batches without enough points outside the band.
_MAX_BATCHES = 64
# REQ-OFF-030, test 2: research 02's band for Booleans read as the 2.83 grid units a Clipper2 call
# moves a vertex (REQ-G2D-030, SRC-118), rounded up to 3 (ours, offset2d SPEC).
_BOOLEAN_BAND_GRID_UNITS = 3


@dataclass(frozen=True, slots=True)
class _Curves:
    """The loops as a chord polygon (P0 → E → P1 per row, E = P1 for lines), the straight
    pieces of the true curves, and the circular arcs from P0 to E with their chords."""

    edge_a: Points  # (e, 2) polygon edges, the P0 → E of every row first, then every E → P1
    edge_b: Points
    edge_loop: NDArray[np.int64]  # (e,) the loop of each edge
    straight: Mask  # (e,) the edges that are pieces of the true curves and not too short to measure
    arc_rows: NDArray[np.int64]  # (A,) the arc rows; also the index of each chord P0 → E
    centre: Points  # (A, 2)
    radius: NDArray[np.float64]  # (A,) |P0 - C|
    turn: NDArray[np.float64]  # (A,) in [0, 2π]
    direction: NDArray[np.float64]  # (A,) +1 counter-clockwise, -1 clockwise
    full: Mask  # (A,) a full circle: its chord has length 0
    loop_count: int


def _cross(ux: ArrayLike, uy: ArrayLike, vx: ArrayLike, vy: ArrayLike) -> NDArray[np.float64]:
    return np.asarray(ux) * np.asarray(vy) - np.asarray(uy) * np.asarray(vx)


def _curves(loops: CurveRows) -> _Curves:
    rows = np.asarray(loops.rows, dtype=np.float64)
    m = rows.shape[0]
    loop_of = (
        np.searchsorted(np.asarray(loops.row_starts), np.arange(m, dtype=np.int64), side="right")
        - 1
    )
    p0, p1, sweep = rows[:, 0:2], rows[:, 2:4], rows[:, 6]
    arc = np.flatnonzero(sweep != 0.0)
    c, a0, a1 = rows[arc, 4:6], p0[arc], p1[arc]
    radius = np.hypot(a0[:, 0] - c[:, 0], a0[:, 1] - c[:, 1])
    v1 = a1 - c
    r1 = np.hypot(v1[:, 0], v1[:, 1])
    off = (r1 != radius) & (r1 > 0.0)
    scale = np.divide(radius, r1, out=np.ones_like(radius), where=off)
    end = np.where(off[:, None], c + v1 * scale[:, None], a1)  # E, where the arc meets the ray
    direction = np.sign(sweep[arc])
    v0, ve = a0 - c, end - c
    dot = v0[:, 0] * ve[:, 0] + v0[:, 1] * ve[:, 1]
    raw = np.mod(
        direction * np.arctan2(_cross(v0[:, 0], v0[:, 1], ve[:, 0], ve[:, 1]), dot), math.tau
    )
    turn = np.clip(raw + math.tau * np.round((np.abs(sweep[arc]) - raw) / math.tau), 0.0, math.tau)
    e = p1.copy()
    e[arc] = end
    edge_a, edge_b = np.concatenate([p0, e]), np.concatenate([e, p1])
    # A piece whose squared length underflows to 0 (shorter than 1e-154 mm) is left out: it lies
    # within that length of the pieces it joins.
    straight = (edge_b[:, 0] - edge_a[:, 0]) ** 2 + (edge_b[:, 1] - edge_a[:, 1]) ** 2 > 0.0
    straight[arc] = False  # a chord is not a piece of the curve
    return _Curves(
        edge_a=edge_a,
        edge_b=edge_b,
        edge_loop=np.concatenate([loop_of, loop_of]).astype(np.int64),
        straight=straight,
        arc_rows=arc.astype(np.int64),
        centre=c,
        radius=radius,
        turn=turn,
        direction=direction,
        full=np.all(end == a0, axis=1),
        loop_count=int(np.asarray(loops.row_starts).size),
    )


def _segment_distance(q: Points, a: Points, b: Points) -> NDArray[np.float64]:
    """(n, s): each point's distance to each segment a → b (all of non-zero length)."""
    dx, dy = b[:, 0] - a[:, 0], b[:, 1] - a[:, 1]
    rx, ry = q[:, 0:1] - a[:, 0], q[:, 1:2] - a[:, 1]
    t = np.clip((rx * dx + ry * dy) / (dx * dx + dy * dy), 0.0, 1.0)
    return np.hypot(rx - t * dx, ry - t * dy)


def _arc_distance(q: Points, cv: _Curves) -> NDArray[np.float64]:
    """(n, A): each point's distance to each arc from P0 to E: to the circle where the point's
    direction from C lies within the turn, else to the nearer end."""
    a0, end = cv.edge_a[cv.arc_rows], cv.edge_b[cv.arc_rows]
    wx, wy = q[:, 0:1] - cv.centre[:, 0], q[:, 1:2] - cv.centre[:, 1]
    vx, vy = a0[:, 0] - cv.centre[:, 0], a0[:, 1] - cv.centre[:, 1]
    angle = np.mod(cv.direction * np.arctan2(_cross(vx, vy, wx, wy), vx * wx + vy * wy), math.tau)
    circle = np.abs(np.hypot(wx, wy) - cv.radius)
    ends = np.minimum(
        np.hypot(q[:, 0:1] - a0[:, 0], q[:, 1:2] - a0[:, 1]),
        np.hypot(q[:, 0:1] - end[:, 0], q[:, 1:2] - end[:, 1]),
    )
    return np.where(angle <= cv.turn, circle, ends)


def _as_points(points: ArrayLike) -> Points:
    return np.asarray(points, dtype=np.float64).reshape(-1, 2)


def distance_to_curves(points: ArrayLike, loops: CurveRows) -> NDArray[np.float64]:
    """d(p, B): each point's distance to the nearest true line or arc of `loops` (Held's clearance,
    research 02, Definitions), within 64·ε·S (module docstring)."""
    q, cv = _as_points(points), _curves(loops)
    a, b = cv.edge_a[cv.straight], cv.edge_b[cv.straight]
    out = np.empty(q.shape[0])
    for start in range(0, q.shape[0], _CHUNK):
        block = q[start : start + _CHUNK]
        nearest = np.min(_segment_distance(block, a, b), axis=1, initial=np.inf)
        arcs = np.min(_arc_distance(block, cv), axis=1, initial=np.inf)
        out[start : start + _CHUNK] = np.minimum(nearest, arcs)
    return out


def dense_loops(loops: CurveRows, sagitta_mm: float) -> list[Points]:
    """Each loop as a closed polygon (last vertex not repeated) whose vertices lie on the true
    curves, arcs cut into equal steps of sagitta at most `sagitta_mm` = s, so the polygon and the
    true curves lie within s of each other both ways, or about 1.56·s where an arc's end is left
    out below; 2s bounds both (test 20 hands it to shapely; `test_offset2d_dense_loops.py`)."""
    cv = _curves(loops)
    m = np.asarray(loops.rows).shape[0]
    pieces: list[list[Points]] = [[] for _ in range(cv.loop_count)]
    arc_of = np.full(m, -1, dtype=np.int64)
    arc_of[cv.arc_rows] = np.arange(cv.arc_rows.size)
    for row in range(m):  # a test helper over a few hundred rows, not the product's kernel
        out = pieces[int(cv.edge_loop[row])]
        k = int(arc_of[row])
        if k < 0:
            out.append(cv.edge_a[row : row + 1])
            continue
        r, turn = float(cv.radius[k]), float(cv.turn[k])
        step = 2.0 * math.acos(max(-1.0, 1.0 - sagitta_mm / r))  # chord with that sagitta
        n = max(1, math.ceil(turn / step))
        v0 = cv.edge_a[row] - cv.centre[k]
        angles = math.atan2(v0[1], v0[0]) + cv.direction[k] * turn * np.arange(n) / n
        out.append(cv.centre[k] + r * np.column_stack([np.cos(angles), np.sin(angles)]))
        out[-1][0] = cv.edge_a[row]  # P0 itself, not its rounded copy
        # E, then the radial connector to P1; an E within s of P1 is left out (a near duplicate
        # vertex breaks GEOS's noding): the last chord then ends up to s off, about 1.56·s.
        if math.dist(cv.edge_b[row], cv.edge_b[m + row]) > sagitta_mm:
            out.append(cv.edge_b[row : row + 1])
    return [np.concatenate(p) for p in pieces]


def _one_hot(index: NDArray[np.int64], k: int) -> NDArray[np.int64]:
    return (index[:, None] == np.arange(k)).astype(np.int64)


def _windings(q: Points, cv: _Curves) -> NDArray[np.int64]:
    """(n, k): each loop's winding number about each point, as the chord polygon's (Sunday's
    crossing rule, half-open in y) plus ±1 per circular segment between a chord and its arc that
    holds the point."""
    ax, ay, bx, by = cv.edge_a[:, 0], cv.edge_a[:, 1], cv.edge_b[:, 0], cv.edge_b[:, 1]
    qx, qy = q[:, 0:1], q[:, 1:2]
    side = _cross(bx - ax, by - ay, qx - ax, qy - ay)  # orient2d(a, b, q)
    up = (ay <= qy) & (qy < by) & (side > 0.0)
    down = (by <= qy) & (qy < ay) & (side < 0.0)
    polygon = up.astype(np.int64) - down.astype(np.int64)
    # Each chord P0 → E with the side its arc's segment lies on; 0 broken as Sunday's rule does.
    chord = cv.arc_rows
    dx, dy = bx[chord] - ax[chord], by[chord] - ay[chord]
    tie = np.where(dy != 0.0, -np.sign(dy), np.sign(dx))
    sign = np.where(side[:, chord] != 0.0, np.sign(side[:, chord]), tie)
    cx, cy = cv.centre[:, 0], cv.centre[:, 1]
    in_disc = (qx - cx) ** 2 + (qy - cy) ** 2 < cv.radius**2
    segment = in_disc & (cv.full | (cv.direction * sign < 0.0))
    arcs = segment.astype(np.int64) * cv.direction.astype(np.int64)
    k = cv.loop_count
    return polygon @ _one_hot(cv.edge_loop, k) + arcs @ _one_hot(cv.edge_loop[chord], k)


def inside_region(points: ArrayLike, loops: CurveRows) -> Mask:
    """p ∈ R: True where an odd number of loops wind about p, whatever their orientation (the
    loops must be simple and must not cross, as the loop tree requires; research 01, rule 5).
    Exact at points farther than 64·ε·S from the curves (module docstring)."""
    q, cv = _as_points(points), _curves(loops)
    out = np.empty(q.shape[0], dtype=np.bool_)
    for start in range(0, q.shape[0], _CHUNK):
        windings = _windings(q[start : start + _CHUNK], cv)
        out[start : start + _CHUNK] = np.count_nonzero(windings, axis=1) % 2 == 1
    return out


def in_offset(points: ArrayLike, loops: CurveRows, kind: RegionKind, t_mm: float) -> Mask:
    """Membership of the offset by research 02, Definitions (Held, Def. 7.1): a region of air
    shrinks, p ∈ R and d(p, B) >= t; a region of material grows, d(p, R) <= t, that is p ∈ R or
    d(p, B) <= t. B is every loop at once, islands included."""
    if not (math.isfinite(t_mm) and t_mm >= 0.0):
        raise ValueError(f"t must be finite and >= 0, got {t_mm!r}")
    inside = inside_region(points, loops)
    distance = distance_to_curves(points, loops)
    if kind is RegionKind.AIR:
        return inside & (distance >= t_mm)
    return inside | (distance <= t_mm)


def in_boolean(op: BooleanName, inside_a: Mask, inside_b: Mask) -> Mask:
    """op(inside(a), inside(b)) (research 02, test 2): union, difference a - b, intersection."""
    if op == "UNION":
        return inside_a | inside_b
    if op == "DIFFERENCE":
        return inside_a & ~inside_b
    if op == "INTERSECTION":
        return inside_a & inside_b
    raise ValueError(f"unknown Boolean operation {op!r}")


class DistanceBand(NamedTuple):
    """The points whose distance d from the curves satisfies |d - t| <= half_width."""

    t_mm: float
    half_width_mm: float

    def holds(self, distance: NDArray[np.float64]) -> Mask:
        return np.abs(distance - self.t_mm) <= self.half_width_mm


def sample_outside_band(
    loops: CurveRows, band: DistanceBand, box: BoxMM, n: int, seed: int
) -> Points:
    """n points drawn uniformly in `box` with NumPy's default generator seeded by `seed`, keeping
    only those outside `band` from the true curves of `loops`, in the order drawn. Raises
    ValueError when too few points lie outside the band to reach n."""
    rng = np.random.default_rng(seed)
    low, high = (box[0], box[1]), (box[2], box[3])
    kept: list[Points] = []
    count = 0
    for _ in range(_MAX_BATCHES):
        q = rng.uniform(low, high, size=(max(n, 1024), 2))
        q = q[~band.holds(distance_to_curves(q, loops))]
        kept.append(q)
        count += q.shape[0]
        if count >= n:
            return np.concatenate(kept)[:n]
    raise ValueError(f"only {count} of {n} points lie outside {band} in {box}")


def polygon_rows(points: ArrayLike, loop_starts: ArrayLike) -> CurveRows:
    """A polygon region's loops (geometry2d's `PolygonRegion` arrays) as line rows, each loop
    closed by an edge from its last vertex to its first, so the oracles read Clipper2's results."""
    p = _as_points(points)
    starts = np.asarray(loop_starts, dtype=np.int64)
    ends = np.append(starts[1:], p.shape[0])
    following = np.arange(1, p.shape[0] + 1, dtype=np.int64)
    following[ends - 1] = starts  # each loop's last vertex closes back to its first
    rows = np.column_stack(
        [p, p[following], np.full((p.shape[0], 2), np.nan), np.zeros(p.shape[0])]
    )
    return CurveRows(rows, np.arange(p.shape[0], dtype=np.int64), starts)


def both_operands(a: CurveRows, b: CurveRows) -> CurveRows:
    """The loops of two operands as one set, for the distance of a point to either (test 2)."""
    starts = np.concatenate([a.row_starts, b.row_starts + a.rows.shape[0]])
    return CurveRows(np.concatenate([a.rows, b.rows]), np.concatenate([a.ids, b.ids]), starts)


def arc_tol_mm(tolerances: ToleranceSet) -> float:
    """a = max(0.05·tol, 2u), Clipper2's ArcTolerance (D-058, D-132, D-146), computed from the
    declared defaults, independently of foundation's `arc_tol_mm` (REQ-FND-011), which the
    oracles' self-tests compare with it."""
    share = TOLERANCE_DEFAULTS["arc_tol_share"].default
    floor = TOLERANCE_DEFAULTS["arc_tol_floor_grid_units"].default * tolerances.grid_unit_mm
    return max(share * tolerances.chord_tol_mm, floor)


def offset_band_mm(tolerances: ToleranceSet) -> float:
    """a + 6u: the width of REQ-OFF-025's band [t, t + a + 6u] from the flattened input (D-132;
    the 6u is foundation's declared rounding margin)."""
    margin = TOLERANCE_DEFAULTS["rounding_margin_grid_units"].default * tolerances.grid_unit_mm
    return arc_tol_mm(tolerances) + margin


def true_curve_band_mm(tolerances: ToleranceSet) -> float:
    """a + 6u + t_flat: the band's width measured against the true lines and arcs, which oracles
    of REQ-OFF-020 exclude (offset2d SPEC, Requirements, preamble); equally the width of
    `grow_chain`'s band from the flattened chain (REQ-OFF-027)."""
    return offset_band_mm(tolerances) + tolerances.flatten_tol_mm


def boolean_band_mm(tolerances: ToleranceSet) -> float:
    """3u: test 2 samples points farther than this from every edge of either operand
    (REQ-OFF-030)."""
    return _BOOLEAN_BAND_GRID_UNITS * tolerances.grid_unit_mm
