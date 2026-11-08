# SPDX-License-Identifier: Apache-2.0
"""Approach points (REQ-SHT-010, 011; research 10, Method 2) and witness marks (REQ-SHT-015;
AQ-016 item 7) of one operation, from its moves."""

import math

import numpy as np
from numpy.typing import NDArray

from splintercam.cl import ClMoves, ClOperation, MoveKind, Role
from splintercam.model import StockBox

from ._checks import PREFIX
from ._types import ApproachPoint, Side, WitnessMark

_SIDES = (Side.MINUS_X, Side.PLUS_X, Side.MINUS_Y, Side.PLUS_Y)


def move_starts(moves: ClMoves) -> NDArray[np.float64]:
    # cl SPEC, Public interface: move 0 has none, move 1 starts at move 0's end (NaN, NaN, z).
    starts = np.full_like(moves.end_mm, np.nan)
    starts[1:] = moves.end_mm[:-1]
    return starts


def _groups(keys: NDArray[np.float64]) -> tuple[int, NDArray[np.int64]]:
    """The number of distinct rows of `keys` and each row's group: exact, and + 0.0 turns -0.0
    into +0.0 so the two are one (DEC-CL-004); callers keep the first value met."""
    if len(keys) == 0:
        return 0, np.zeros(0, dtype=np.int64)
    unique, inverse = np.unique(keys + 0.0, axis=0, return_inverse=True)
    return len(unique), inverse.reshape(-1).astype(np.int64)


def _side_and_gap(
    x: float, y: float, stock: StockBox, radius: float, name: str
) -> tuple[Side | None, float | None, float | None]:
    lo, hi = stock.min_mm, stock.max_mm
    dx, dy = max(lo[0] - x, 0.0, x - hi[0]), max(lo[1] - y, 0.0, y - hi[1])
    if dx * dx + dy * dy <= radius * radius:  # toolpath REQ-TP-012's expression, in its order
        raise ValueError(
            f"{PREFIX}operation {name!r}: REQ-SHT-011: approach point X {x} Y {y} "
            f"lies within R {radius} of the stock box"
        )
    beyond = (x < lo[0], x > hi[0], y < lo[1], y > hi[1])
    outside = [s for s, out in zip(_SIDES, beyond, strict=True) if out]
    distance = math.sqrt(dx * dx + dy * dy)
    return (outside[0] if len(outside) == 1 else Side.CORNER), distance, distance - radius


def approach_points(
    written: ClOperation, stock: StockBox, radius: float
) -> tuple[ApproachPoint, ...]:
    header, moves = written.header, written.moves
    feed_values = np.array([value for _, value in header.feed_classes], dtype=np.float64)
    end, kind, starts = moves.end_mm, moves.kind, move_starts(moves)
    down = end[:, 2] < starts[:, 2]  # DEC-SHT-009: only moves going down; NaN start: False
    rapid_low = (kind == MoveKind.RAPID) & (end[:, 2] < header.clearance_height_mm) & down
    z_alone = (starts[:, 0] == end[:, 0]) & (starts[:, 1] == end[:, 1])  # NaN starts: False
    chosen = np.flatnonzero(rapid_low | z_alone)
    count, group = _groups(end[chosen, :2])
    is_rapid = rapid_low[chosen]
    first = np.full(count, len(end), dtype=np.int64)
    np.minimum.at(first, group[is_rapid], chosen[is_rapid])
    rapid_to, lowest = np.full(count, np.inf), np.full(count, np.inf)
    np.minimum.at(rapid_to, group[is_rapid], end[chosen[is_rapid], 2])
    # Every RAPID ending below h_c moves along Z alone (cl REQ-CL-022), so it counts here too.
    np.minimum.at(lowest, group, end[chosen, 2])
    descents = np.bincount(group[is_rapid], minlength=count)
    plunges = (kind[chosen] == MoveKind.LINE) & z_alone[chosen] & down[chosen]
    feeds: list[list[float]] = [[] for _ in range(count)]
    used = feed_values[moves.feed_class[chosen[plunges]]]
    pairs = np.column_stack((group[plunges].astype(np.float64), used))
    firsts = np.unique(pairs, axis=0, return_index=True)[1] if len(pairs) else np.zeros(0, int)
    for index in np.sort(firsts):  # order of first use
        feeds[int(group[plunges][index])].append(float(used[index]))
    points: list[ApproachPoint] = []
    for g in sorted(np.flatnonzero(first < len(end)), key=lambda g: first[g]):
        x, y, low = float(end[first[g], 0]), float(end[first[g], 1]), float(lowest[g])
        below = low < stock.top_mm
        side = _side_and_gap(x, y, stock, radius, header.name) if below else (None, None, None)
        descent = (int(descents[g]), float(rapid_to[g]), low, tuple(feeds[g]))
        points.append(ApproachPoint(x, y, *descent, *side))
    return tuple(points)


def witness_marks(moves: ClMoves, radius: float) -> tuple[WitnessMark, ...]:
    """REQ-SHT-015 (DEC-SHT-003, DEC-SHT-012): where a CUT follows a LINE of role APPROACH that
    moves toward the wall, the tool touches it at S + R·n, n the CUT's unit normal at S on the
    side the approach moves to."""
    kind, role, end = moves.kind, moves.role, moves.end_mm
    approach_line = (kind[:-1] == MoveKind.LINE) & (role[:-1] == Role.APPROACH)
    lead = np.flatnonzero(approach_line & (role[1:] == Role.CUT))
    cut, s = lead + 1, end[lead, :2]
    step = s - move_starts(moves)[lead, :2]
    tangent = end[cut, :2] - s
    across = np.column_stack((-tangent[:, 1], tangent[:, 0]))  # a LINE's normal
    normal = np.where((kind[cut] == MoveKind.ARC)[:, None], s - moves.centre_mm[cut], across)
    toward = normal[:, 0] * step[:, 0] + normal[:, 1] * step[:, 1]
    keep = toward != 0.0  # no XY step, a cut along Z, or an approach along the wall: no mark
    s, normal = s[keep], normal[keep] * np.sign(toward[keep])[:, None]
    n = normal / np.sqrt(normal[:, 0] * normal[:, 0] + normal[:, 1] * normal[:, 1])[:, None]
    marks = np.column_stack((s, s + radius * n))
    count, group = _groups(marks)
    first = np.sort(np.unique(group, return_index=True)[1])
    passes = np.bincount(group, minlength=count)[group[first]]
    rows: list[list[float]] = marks[first].tolist()
    return tuple(
        WitnessMark(sx, sy, cx, cy, int(p))
        for (sx, sy, cx, cy), p in zip(rows, passes, strict=True)
    )
