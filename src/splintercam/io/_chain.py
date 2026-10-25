# SPDX-License-Identifier: Apache-2.0
"""Chaining DXF curve rows into one closed contour (research 21, Methods 5 and 6; REQ-IO-017 to
026). A fixed rule (ours) until topic 25 releases its chaining tolerance: exact duplicates are
dropped, row ends are matched in two stages, a junction snaps one row's end onto the other's
bounded by B, and exactly one closed chain must remain.

End matching and the move checks (sqrt and products only) run in NumPy over all rows; the
re-placing of a moved arc's centre runs in geometry2d's C++ kernel (`rows_from_sweeps`). The
bookkeeping over the resulting rows and junctions is Python, like the loop over ezdxf entities:
this is the provisional chain reconstruction, not a kernel hot path (DEC-IO-005)."""

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import TOLERANCE_DEFAULTS, Context, Severity
from splintercam.geometry2d import Box, row_boxes, rows_from_sweeps

from . import _diagnostics as diag

_SEG_BITS = 16
_ROW_WIDTH = 7

type _Ends = tuple[NDArray[np.float64], NDArray[np.float64]]  # a row's (p0, p1) after a move


@dataclass(frozen=True, slots=True)
class _Env:
    """The tolerances and sinks the chaining threads through: eps_len and eps_ang (mm, rad), the
    gap limit (mm), the computation `Context` and the diagnostic `Collector`."""

    eps: float
    eps_ang: float
    gap: float
    ctx: Context
    collector: diag.Collector


def _entity_segment(source_id: int) -> tuple[int, int]:
    return source_id >> _SEG_BITS, source_id & ((1 << _SEG_BITS) - 1)


def _dist(a: NDArray[np.float64], b: NDArray[np.float64]) -> float:
    # sqrt of a sum of squares, like geometry2d's `distance`: correctly-rounded operations only,
    # the same on every platform; never `hypot` in a tolerance decision (D-055; SPEC split rule).
    dx, dy = float(a[0]) - float(b[0]), float(a[1]) - float(b[1])
    return math.sqrt(dx * dx + dy * dy)


def _magnification(row: NDArray[np.float64]) -> float:
    """D/c of a row (REQ-IO-020): 1 for a line or an arc of |φ| <= π, else 2r/c, how much
    re-placing an end on the bisector magnifies the move. For |φ| > π, D = c/sin(|φ|/2) = 2r since
    the chord c = 2r·sin(|φ|/2), so no transcendental is needed (D-055; ours, derived)."""
    sweep = abs(float(row[6]))
    if sweep == 0.0 or sweep <= math.pi:
        return 1.0
    radius = _dist(row[0:2], row[4:6])
    chord = _dist(row[0:2], row[2:4])
    return 2.0 * radius / chord


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, item: int) -> int:
        root = item
        while self._parent[root] != root:
            self._parent[root] = self._parent[self._parent[root]]
            root = self._parent[root]
        return root

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


# --- duplicates (REQ-IO-017) ---------------------------------------------------------------------


def _canonical_key(row: NDArray[np.float64], eps: float, eps_ang: float) -> tuple[object, ...]:
    # An order-independent key on a grid of eps (coordinates) and eps_ang (sweep): exact duplicates
    # land in the same bucket. Swapping an arc's ends negates its sweep (REQ-IO-017).
    def grid(value: float, step: float) -> int:
        return round(float(value) / step)

    p0 = (grid(row[0], eps), grid(row[1], eps))
    p1 = (grid(row[2], eps), grid(row[3], eps))
    sweep = float(row[6])
    if sweep == 0.0:
        return ("line", *sorted((p0, p1)))
    (lo, hi), signed = ((p0, p1), sweep) if p0 <= p1 else ((p1, p0), -sweep)
    centre = (grid(row[4], eps), grid(row[5], eps))
    return ("arc", lo, hi, centre, grid(signed, eps_ang))


def _dedup(rows: NDArray[np.float64], ids: NDArray[np.int64],
           env: _Env) -> tuple[NDArray[np.float64], NDArray[np.int64]]:  # fmt: skip
    buckets: dict[tuple[object, ...], list[int]] = {}
    for position in range(rows.shape[0]):
        buckets.setdefault(_canonical_key(rows[position], env.eps, env.eps_ang), []).append(
            position
        )
    keep = np.ones(rows.shape[0], dtype=bool)
    for members in buckets.values():
        if len(members) == 1:
            continue
        kept = min(members, key=lambda position: int(ids[position]))
        for position in members:
            if position == kept:
                continue
            keep[position] = False
            entity, segment = _entity_segment(int(ids[position]))
            env.collector.entity(diag.DXF_DUPLICATE, Severity.INFO, entity, segment,
                                 f"duplicate of source {int(ids[kept])}, dropped")  # fmt: skip
    return rows[keep], ids[keep]


# --- two-stage end matching (REQ-IO-018, 019) ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Match:
    """The matching of row ends: `junctions` are endpoint-index pairs (e_a, e_b); `endpoint_row`
    maps an endpoint index to its row; `points` are the endpoint coordinates; `branch` is set when
    a T, a crossing or an ambiguous gap was reported (REQ-IO-019)."""

    junctions: list[tuple[int, int]]
    endpoint_row: NDArray[np.int64]
    points: NDArray[np.float64]
    branch: bool


def _endpoint_points(
    rows: NDArray[np.float64], open_rows: NDArray[np.int64]
) -> NDArray[np.float64]:
    points = np.empty((2 * open_rows.size, 2), dtype=np.float64)
    points[0::2] = rows[open_rows, 0:2]
    points[1::2] = rows[open_rows, 2:4]
    return points


def _distances(points: NDArray[np.float64]) -> NDArray[np.float64]:
    diff = points[:, None, :] - points[None, :, :]
    dist = np.sqrt(diff[..., 0] ** 2 + diff[..., 1] ** 2)  # sqrt of squares, never hypot (D-055)
    size = points.shape[0]
    both = np.arange(size, dtype=np.intp)
    dist[both, both] = np.inf  # not itself
    dist[both, both ^ 1] = np.inf  # the two ends of one row never partner (REQ-IO-018)
    return dist


def _stage_one(dist: NDArray[np.float64], endpoint_row: NDArray[np.int64],
               points: NDArray[np.float64], env: _Env
               ) -> tuple[list[tuple[int, int]], set[int], bool]:  # fmt: skip
    size = dist.shape[0]
    union = _UnionFind(size)
    for a, b in zip(*np.where(dist <= env.eps), strict=True):
        union.union(int(a), int(b))
    clusters: dict[int, list[int]] = {}
    for endpoint in range(size):
        clusters.setdefault(union.find(endpoint), []).append(endpoint)
    junctions: list[tuple[int, int]] = []
    unmatched: set[int] = set()
    branch = False
    for members in clusters.values():
        rows_in = {int(endpoint_row[member]) for member in members}
        if len(members) == 1:
            unmatched.add(members[0])
        elif len(members) == 2 and len(rows_in) == 2:
            junctions.append((members[0], members[1]))
        elif len(members) >= 3:
            branch = True
            cx, cy = (float(value) for value in points[members].mean(axis=0))
            message = f"{len(members)} ends meet (a T or crossing)"
            env.collector.junction(diag.DXF_BRANCH, Severity.ERROR, cx, cy, message)
    return junctions, unmatched, branch


def _stage_two(dist: NDArray[np.float64], unmatched: set[int], points: NDArray[np.float64],
               env: _Env) -> tuple[list[tuple[int, int]], bool]:  # fmt: skip
    order = sorted(unmatched)
    candidates: dict[int, list[int]] = {}
    for endpoint in order:
        near = [other for other in order
                if other != endpoint and env.eps < dist[endpoint, other] <= env.gap]  # fmt: skip
        candidates[endpoint] = near
    branch = False
    for endpoint in order:
        if len(candidates[endpoint]) >= 2:
            branch = True
            px, py = float(points[endpoint, 0]), float(points[endpoint, 1])
            env.collector.junction(diag.DXF_BRANCH, Severity.ERROR, px, py,
                                   "an end has two gap candidates")  # fmt: skip
    junctions: list[tuple[int, int]] = []
    for endpoint in order:
        near = candidates[endpoint]
        if len(near) == 1 and candidates[near[0]] == [endpoint] and endpoint < near[0]:
            junctions.append((endpoint, near[0]))
    return junctions, branch


def _match(rows: NDArray[np.float64], env: _Env) -> _Match:
    open_rows = np.flatnonzero(np.abs(rows[:, 6]) != math.tau).astype(np.int64)
    points = _endpoint_points(rows, open_rows)
    endpoint_row = np.repeat(open_rows, 2)
    if points.shape[0] == 0:
        return _Match([], endpoint_row, points, branch=False)
    dist = _distances(points)
    stage1, unmatched, branch1 = _stage_one(dist, endpoint_row, points, env)
    stage2, branch2 = _stage_two(dist, unmatched, points, env)
    return _Match(stage1 + stage2, endpoint_row, points, branch1 or branch2)


# --- junction moves (REQ-IO-020, 021, 022) -------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Junction:
    endpoints: tuple[int, int]
    mover_row: int
    which: int
    target: NDArray[np.float64]
    gap_mm: float


@dataclass(frozen=True, slots=True)
class _Moves:
    rows: NDArray[np.float64]
    partner: dict[int, int]
    refused: bool


def _decide(rows: NDArray[np.float64], ids: NDArray[np.int64], match: _Match) -> list[_Junction]:
    decided: list[_Junction] = []
    for e_a, e_b in match.junctions:
        ra, rb = int(match.endpoint_row[e_a]), int(match.endpoint_row[e_b])
        key_a = (_magnification(rows[ra]), -int(ids[ra]))
        key_b = (_magnification(rows[rb]), -int(ids[rb]))
        keeper, mover = (e_a, e_b) if key_a >= key_b else (e_b, e_a)
        gap_mm = _dist(match.points[mover], match.points[keeper])
        decided.append(_Junction((e_a, e_b), int(match.endpoint_row[mover]), mover % 2,
                                  match.points[keeper].copy(), gap_mm))  # fmt: skip
    return decided


def _classify_rows(rows: NDArray[np.float64], decided: list[_Junction], eps: float, gap: float
                   ) -> tuple[dict[int, str], dict[int, float], dict[int, _Ends]]:  # fmt: skip
    moves: dict[int, dict[int, NDArray[np.float64]]] = {}
    for junction in decided:
        moves.setdefault(junction.mover_row, {})[junction.which] = junction.target
    row_class: dict[int, str] = {}
    row_b: dict[int, float] = {}
    new_ends: dict[int, _Ends] = {}
    for row, ends in moves.items():
        p0, p1 = rows[row, 0:2], rows[row, 2:4]
        new0 = ends.get(0, p0)
        new1 = ends.get(1, p1)
        shift = _dist(new0, p0) + _dist(new1, p1)
        b_mm = shift * _magnification(rows[row])
        new_chord = _dist(new1, new0)
        row_class[row] = _classify(b_mm, new_chord, eps, gap)
        row_b[row] = b_mm
        new_ends[row] = (np.asarray(new0, dtype=np.float64), np.asarray(new1, dtype=np.float64))
    return row_class, row_b, new_ends


def _classify(b_mm: float, new_chord: float, eps: float, gap: float) -> str:
    if new_chord <= eps:
        return "refused"
    if b_mm <= 3.0 * eps:
        return "silent"
    if b_mm <= gap:
        return "closed"
    return "refused"


def _apply_moves(rows: NDArray[np.float64], ids: NDArray[np.int64], match: _Match,
                 env: _Env) -> _Moves:  # fmt: skip
    decided = _decide(rows, ids, match)
    row_class, row_b, new_ends = _classify_rows(rows, decided, env.eps, env.gap)
    out = rows.copy()
    arc_rows = [row for row in new_ends
                if row_class[row] != "refused" and out[row, 6] != 0.0]  # fmt: skip
    for row, (new0, new1) in new_ends.items():
        if row_class[row] != "refused":
            out[row, 0:2], out[row, 2:4] = new0, new1
    if arc_rows:
        p0 = np.array([new_ends[row][0] for row in arc_rows], dtype=np.float64)
        p1 = np.array([new_ends[row][1] for row in arc_rows], dtype=np.float64)
        sweeps = rows[arc_rows, 6]
        built = rows_from_sweeps(p0, p1, sweeps, env.ctx)
        for position, row in enumerate(arc_rows):
            out[row] = built.rows[position]
    partner: dict[int, int] = {}
    refused = False
    for junction in decided:
        cls = row_class[junction.mover_row]
        tx, ty = float(junction.target[0]), float(junction.target[1])
        b_mm = row_b[junction.mover_row]
        gap_note = f"gap {junction.gap_mm:.4g} mm, move B {b_mm:.4g} mm"
        if cls == "refused":
            refused = True
            env.collector.junction(diag.DXF_GAP_NOT_CLOSED, Severity.ERROR, tx, ty,
                                   f"not closed ({gap_note})")  # fmt: skip
        else:
            partner[junction.endpoints[0]] = junction.endpoints[1]
            partner[junction.endpoints[1]] = junction.endpoints[0]
            if cls == "closed":
                env.collector.junction(diag.DXF_GAP_CLOSED, Severity.WARNING, tx, ty,
                                       f"closed ({gap_note})")  # fmt: skip
    return _Moves(out, partner, refused)


# --- chaining and contour selection (REQ-IO-024, 026) --------------------------------------------


def _open_position(match: _Match) -> dict[int, int]:
    position: dict[int, int] = {}
    for endpoint in range(0, match.points.shape[0], 2):
        position[int(match.endpoint_row[endpoint])] = endpoint
    return position


def _components(match: _Match, partner: dict[int, int]) -> list[list[int]]:
    size = match.points.shape[0]
    union = _UnionFind(size)
    for endpoint in range(0, size, 2):
        union.union(endpoint, endpoint + 1)
    for a, b in partner.items():
        union.union(a, b)
    groups: dict[int, list[int]] = {}
    for endpoint in range(size):
        groups.setdefault(union.find(endpoint), []).append(endpoint)
    return list(groups.values())


def _rows_of(match: _Match, members: list[int]) -> list[int]:
    return sorted({int(match.endpoint_row[endpoint]) for endpoint in members})


def box_of_rows(rows: NDArray[np.float64], ctx: Context) -> Box:
    """The axis-aligned box of curve rows (mm), from geometry2d's row boxes (REQ-IO-006, 027)."""
    boxes = row_boxes(rows, ctx)
    return Box(float(boxes[:, 0].min()), float(boxes[:, 1].min()),
               float(boxes[:, 2].max()), float(boxes[:, 3].max()))  # fmt: skip


def _order_closed(rows: NDArray[np.float64], ids: NDArray[np.int64], match: _Match,
                  partner: dict[int, int], row_indices: list[int]
                  ) -> tuple[NDArray[np.float64], NDArray[np.int64]]:  # fmt: skip
    position = _open_position(match)
    start = min(row_indices, key=lambda row: int(ids[row]))
    if start not in position:  # a full circle is a closed chain of one row (REQ-IO-018)
        return _assemble(rows, ids, [(start, False)])
    order: list[tuple[int, bool]] = []
    current, entry = start, 0
    while True:
        order.append((current, entry == 1))
        exit_endpoint = position[current] + (1 - entry)
        nxt = partner.get(exit_endpoint)
        if nxt is None:
            break
        following = int(match.endpoint_row[nxt])
        if following == start:
            break
        current, entry = following, nxt % 2
    return _assemble(rows, ids, order)


def _assemble(rows: NDArray[np.float64], ids: NDArray[np.int64], order: list[tuple[int, bool]]
              ) -> tuple[NDArray[np.float64], NDArray[np.int64]]:  # fmt: skip
    out_rows = np.empty((len(order), _ROW_WIDTH), dtype=np.float64)
    out_ids = np.empty(len(order), dtype=np.int64)
    for position, (row, reverse) in enumerate(order):
        source = rows[row]
        out_rows[position] = (
            [source[2], source[3], source[0], source[1], source[4], source[5], -source[6]]
            if reverse
            else source
        )
        out_ids[position] = ids[row]
    return out_rows, out_ids


def _select(ids: NDArray[np.int64], match: _Match, moves: _Moves,
            env: _Env) -> tuple[NDArray[np.float64], NDArray[np.int64]] | None:  # fmt: skip
    # The final coordinates come from moves.rows (after the junction snaps), not the input rows.
    closed: list[list[int]] = []
    open_present = False
    for members in _components(match, moves.partner):
        row_indices = _rows_of(match, members)
        if all(endpoint in moves.partner for endpoint in members):
            closed.append(row_indices)
        else:
            open_present = True
            free = [endpoint for endpoint in members if endpoint not in moves.partner]
            ends = ", ".join(f"({match.points[e, 0]:.4g}, {match.points[e, 1]:.4g})" for e in free)
            env.collector.open_chain(min(int(ids[row]) for row in row_indices),
                                     f"open chain, free ends at {ends} mm")  # fmt: skip
    for index in np.flatnonzero(np.abs(moves.rows[:, 6]) == math.tau).tolist():
        closed.append([int(index)])
    if len(closed) != 1:
        boxes = "; ".join(str(box_of_rows(moves.rows[indices], env.ctx)) for indices in closed)
        env.collector.contour_count(
            f"{len(closed)} closed chains" + (f": {boxes}" if boxes else "")
        )
    if len(closed) == 1 and not open_present:
        return _order_closed(moves.rows, ids, match, moves.partner, closed[0])
    return None


def resolve_contour(rows: NDArray[np.float64], ids: NDArray[np.int64], ctx: Context,
                    collector: diag.Collector
                    ) -> tuple[NDArray[np.float64], NDArray[np.int64]] | None:  # fmt: skip
    """Chain the rows into one closed contour, or report why not (REQ-IO-017 to 026). Returns the
    ordered loop rows (m, 7) and their source IDs, or None with error diagnostics collected."""
    env = _Env(ctx.tolerances.length_eps_mm, ctx.tolerances.angle_eps_rad,
               TOLERANCE_DEFAULTS["dxf_gap_close_mm"].default, ctx, collector)  # fmt: skip
    rows, ids = _dedup(rows, ids, env)
    match = _match(rows, env)
    moves = _apply_moves(rows, ids, match, env)
    if match.branch or moves.refused:
        return None
    return _select(ids, match, moves, env)
