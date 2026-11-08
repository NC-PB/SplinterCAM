# SPDX-License-Identifier: Apache-2.0
"""Approach points (REQ-SHT-010, 011; research 10, Method 2) and witness marks (REQ-SHT-015;
AQ-016 item 7) of one operation, from its moves. "Same XY" is exact with +0.0 equal to -0.0
(DEC-CL-004): keys get + 0.0, which turns -0.0 into +0.0; the first value met is kept."""

import math

import numpy as np
from numpy.typing import NDArray

from splintercam.cl import ClMoves, ClOperation, MoveKind, Role
from splintercam.model import StockBox

from ._checks import PREFIX
from ._types import ApproachPoint, Side, WitnessMark

_SIDES = (Side.MINUS_X, Side.PLUS_X, Side.MINUS_Y, Side.PLUS_Y)


def move_starts(moves: ClMoves) -> NDArray[np.float64]:
    """Each move's start (cl SPEC, Public interface): none for move 0, (NaN, NaN, z of move 0)
    for move 1, the previous end after that."""
    starts = np.full_like(moves.end_mm, np.nan)
    if len(starts) > 1:
        starts[1, 2] = moves.end_mm[0, 2]
        starts[2:] = moves.end_mm[1:-1]
    return starts


def _groups(keys: NDArray[np.float64]) -> tuple[int, NDArray[np.int64]]:
    """The number of distinct rows of `keys` and each row's group (exact, -0.0 as +0.0)."""
    if len(keys) == 0:
        return 0, np.zeros(0, dtype=np.int64)
    unique, inverse = np.unique(keys + 0.0, axis=0, return_inverse=True)
    return len(unique), inverse.reshape(-1).astype(np.int64)


def _side_and_gap(
    x: float, y: float, stock: StockBox, radius: float, name: str
) -> tuple[Side, float, float]:
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


def _feeds_per_group(
    groups: NDArray[np.int64], feeds: NDArray[np.float64], count: int
) -> list[tuple[float, ...]]:
    """Per group the distinct feeds in order of first use."""
    per_group: list[list[float]] = [[] for _ in range(count)]
    if len(groups):
        pairs = np.column_stack((groups.astype(np.float64), feeds))
        _, first = np.unique(pairs, axis=0, return_index=True)
        for index in np.sort(first):
            per_group[int(groups[index])].append(float(feeds[index]))
    return [tuple(f) for f in per_group]


def approach_points(
    written: ClOperation, stock: StockBox, radius: float
) -> tuple[ApproachPoint, ...]:
    """REQ-SHT-010 and 011 for one operation; R is the operation's tool radius."""
    header, moves = written.header, written.moves
    feed_values = np.array([value for _, value in header.feed_classes], dtype=np.float64)
    end, kind, starts = moves.end_mm, moves.kind, move_starts(moves)
    rapid_low = (kind == MoveKind.RAPID) & (end[:, 2] < header.clearance_height_mm)
    z_alone = (starts[:, 0] == end[:, 0]) & (starts[:, 1] == end[:, 1])  # NaN starts: False
    chosen = np.flatnonzero(rapid_low | z_alone)
    count, group = _groups(end[chosen, :2])
    is_rapid = rapid_low[chosen]
    first = np.full(count, len(end), dtype=np.int64)
    np.minimum.at(first, group[is_rapid], chosen[is_rapid])
    rapid_to, lowest = np.full(count, np.inf), np.full(count, np.inf)
    np.minimum.at(rapid_to, group[is_rapid], end[chosen[is_rapid], 2])
    np.minimum.at(lowest, group, end[chosen, 2])  # DEC-SHT-009: the RAPIDs count too
    descents = np.bincount(group[is_rapid], minlength=count)
    lines = (kind[chosen] == MoveKind.LINE) & z_alone[chosen]
    feeds = _feeds_per_group(group[lines], feed_values[moves.feed_class[chosen[lines]]], count)
    points: list[ApproachPoint] = []
    for g in sorted(np.flatnonzero(first < len(end)), key=lambda g: first[g]):
        x, y = float(end[first[g], 0]), float(end[first[g], 1])
        low = float(lowest[g])
        # REQ-SHT-011 applies where the tool comes down below the stock top, not above it.
        side = _side_and_gap(x, y, stock, radius, header.name) if low < stock.top_mm else None
        side_values = side or (None, None, None)
        points.append(
            ApproachPoint(x, y, int(descents[g]), float(rapid_to[g]), low, feeds[g], *side_values)
        )
    return tuple(points)


def witness_marks(moves: ClMoves, radius: float) -> tuple[WitnessMark, ...]:
    """REQ-SHT-015: where a CUT follows a LINE of role APPROACH that moves in XY (DEC-SHT-003)."""
    kind, role, end = moves.kind, moves.role, moves.end_mm
    starts = move_starts(moves)
    approach_line = (kind[:-1] == MoveKind.LINE) & (role[:-1] == Role.APPROACH)
    lead = np.flatnonzero(approach_line & (role[1:] == Role.CUT))
    step = end[lead, :2] - starts[lead, :2]
    moving = (step != 0.0).any(axis=1)
    lead, step = lead[moving], step[moving]
    if len(lead) == 0:
        return ()
    u = step / np.sqrt(step[:, 0] * step[:, 0] + step[:, 1] * step[:, 1])[:, None]
    centre = end[lead, :2]
    count, group = _groups(np.column_stack((centre, u)))
    _, first = np.unique(group, return_index=True)
    passes = np.bincount(group, minlength=count)
    contact = centre + radius * u
    return tuple(
        WitnessMark(
            float(centre[i, 0]),
            float(centre[i, 1]),
            float(contact[i, 0]),
            float(contact[i, 1]),
            int(passes[group[i]]),
        )
        for i in np.sort(first)
    )
