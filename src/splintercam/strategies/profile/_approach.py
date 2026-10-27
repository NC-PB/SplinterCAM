# SPDX-License-Identifier: Apache-2.0
"""The start point S, the approach point P and the clockwise loop from S (research 22, Method 2,
4 and 5; DEC-PRF-002, DEC-PRF-003). NumPy over the loop's edges, `sqrt` the only function."""

import math

import numpy as np
from numpy.typing import NDArray

from splintercam.geometry2d import PolygonRegion, orient2d
from splintercam.model import StockBox

type Point = tuple[float, float]


def _longest_line_edge(region: PolygonRegion, arc_ids: NDArray[np.int64]) -> int | None:
    # REQ-PRF-013: an edge whose source ID has no arc row is a line row's (every output ID is
    # a contour ID, REQ-OFF-034); squared lengths, the first in CCW order on a tie (np.argmax).
    p = region.points
    d = np.roll(p, -1, axis=0) - p
    line = ~np.isin(region.source_ids, arc_ids)
    length2 = np.where(line, d[:, 0] * d[:, 0] + d[:, 1] * d[:, 1], -1.0)
    k = int(np.argmax(length2))
    return k if length2[k] >= 0.0 else None


def _unit(x: float, y: float) -> Point:
    length = math.sqrt(x * x + y * y)
    return x / length, y / length


def _outward(a: NDArray[np.float64], b: NDArray[np.float64]) -> Point:
    # The unit outward normal of the CCW edge a → b: its direction turned right.
    return _unit(float(b[1] - a[1]), float(a[0] - b[0]))


def _start(p: NDArray[np.float64], k: int, at_vertex: bool) -> tuple[Point, Point]:
    # S and n: the midpoint of edge k and its normal, or vertex k and the normalised sum of the
    # normals of its two edges (REQ-PRF-014).
    after = p[(k + 1) % p.shape[0]]
    if not at_vertex:
        s = (p[k] + after) / 2.0
        return (float(s[0]), float(s[1])), _outward(p[k], after)
    (ax, ay), (bx, by) = _outward(p[k - 1], p[k]), _outward(p[k], after)
    return (float(p[k, 0]), float(p[k, 1])), _unit(ax + bx, ay + by)


def approach_point(s: Point, n: Point, stock: StockBox, clearance: float) -> Point:
    # REQ-PRF-014, DEC-PRF-003, DEC-PRF-007 (4): S + d·n, n a unit vector, at the ray's exit from
    # the stock box grown by c with round corners; a side with a normal component of 0 skipped.
    (sx, sy), (nx, ny), c = s, n, clearance
    (x0, y0, _), (x1, y1, _) = stock.min_mm, stock.max_mm
    gx, gy = max(x0 - sx, 0.0, sx - x1), max(y0 - sy, 0.0, sy - y1)
    if gx * gx + gy * gy >= c * c:
        return s
    exits = [(edge - start) / step for step, start, edge in
             ((nx, sx, x1 + c if nx > 0.0 else x0 - c), (ny, sy, y1 + c if ny > 0.0 else y0 - c))
             if step != 0.0]  # fmt: skip
    d = max(0.0, min(exits))
    qx, qy = sx + d * nx, sy + d * ny
    if x0 <= qx <= x1 or y0 <= qy <= y1:  # beside a side of the box
        return qx, qy
    # Past a corner: the larger root of |S + d·n - corner|² = c² (convex, so the exit).
    wx, wy = sx - (x0 if qx < x0 else x1), sy - (y0 if qy < y0 else y1)
    b = wx * nx + wy * ny
    d = -b + math.sqrt(max(b * b - (wx * wx + wy * wy - c * c), 0.0))
    return sx + d * nx, sy + d * ny


def _blocked(p: NDArray[np.float64], skip: list[int], s: Point, end: Point) -> bool:
    # REQ-PRF-015: S → P touches or crosses an edge but the ones at S (orient2d, exact).
    keep = np.ones(p.shape[0], dtype=np.bool_)
    keep[np.array(skip, dtype=np.int64)] = False  # -1 is the last edge
    a, b = p[keep], np.roll(p, -1, axis=0)[keep]
    ss, ee = np.broadcast_to(s, a.shape), np.broadcast_to(end, a.shape)
    o1, o2 = orient2d(ss, ee, a), orient2d(ss, ee, b)  # int8 signs: products stay in -1 … 1
    o3, o4 = orient2d(a, b, ss), orient2d(a, b, ee)
    # Collinear: the boxes must overlap in x and y.
    low = np.maximum(np.minimum(a, b), np.minimum(ss, ee))
    high = np.minimum(np.maximum(a, b), np.maximum(ss, ee))
    overlap = (low <= high).all(axis=1)
    collinear = (o1 == 0) & (o2 == 0)
    return bool(((o1 * o2 <= 0) & (o3 * o4 <= 0) & (~collinear | overlap)).any())


def start_and_approach(
    region: PolygonRegion, arc_ids: NDArray[np.int64], stock: StockBox, clearance: float
) -> tuple[NDArray[np.float64] | None, Point]:
    # REQ-PRF-012 to 015: the CW loop from S and P, S on the longest line edge or, when that is
    # blocked or missing, at the smallest vertex; no loop (and that S) when it is blocked too.
    p = region.points
    k = _longest_line_edge(region, arc_ids)
    candidates = [(0, True)] if k is None else [(k, False), (0, True)]
    s: Point = (math.nan, math.nan)
    for k, at_vertex in candidates:
        s, n = _start(p, k, at_vertex)
        end = approach_point(s, n, stock, clearance)
        if end == s or not _blocked(p, [k - 1, k] if at_vertex else [k], s, end):
            return _clockwise(p, k, s, at_vertex), end
    return None, s


def _clockwise(p: NDArray[np.float64], k: int, s: Point, at_vertex: bool) -> NDArray[np.float64]:
    # Research 22, Method 2: offset2d's CCW loop reversed, from S on to v_k, v_k-1, …, back to S.
    order: NDArray[np.int64] = np.mod(k - np.arange(p.shape[0], dtype=np.int64), p.shape[0])
    if at_vertex:
        return p[np.append(order, k)]
    start = np.array([s], dtype=np.float64)
    return np.concatenate([start, p[order], start])
