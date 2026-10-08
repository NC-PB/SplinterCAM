# SPDX-License-Identifier: Apache-2.0
"""Zero-width slits: a run of rows a loop runs out and back exactly, removed so the loop splits
into the loops on either side (REQ-G2D-241; Peter, 2026-10-08, DEC-G2D-039)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import Diagnostic, Severity

from ._rows import CurveRows


@dataclass(frozen=True, slots=True)
class Slits:
    """The loops with their slits removed: `pieces`, per piece its input loop in `origin`, and
    per removed slit its input loop and note."""

    pieces: CurveRows
    origin: NDArray[np.int64]
    notes: tuple[tuple[int, Diagnostic], ...]


def _partners(rows: NDArray[np.float64]) -> NDArray[np.int64]:
    """Per row the one other row that is its exact reverse (end points swapped, the same centre,
    the sweep negated; bit for bit), or -1; never a cyclic neighbour, which is a spike."""
    m = rows.shape[0]
    centre = np.where(rows[:, 6:7] == 0.0, 0.0, rows[:, 4:6])  # a line's NaN centre as 0
    sweep = rows[:, 6:7] + 0.0  # -0.0 becomes 0.0
    forward = np.hstack([rows[:, 0:4], centre, sweep])
    backward = np.hstack([rows[:, 2:4], rows[:, 0:2], centre, -sweep + 0.0])
    _, group = np.unique(np.vstack([forward, backward]).view(np.int64), axis=0, return_inverse=True)
    group = group.reshape(-1)
    count = np.bincount(group[:m], minlength=int(group.max()) + 1)
    row_of = np.full(count.size, -1, dtype=np.int64)
    row_of[group[:m]] = np.arange(m)
    partner: NDArray[np.int64] = np.where(count[group[m:]] == 1, row_of[group[m:]], -1)
    gap = np.remainder(partner - np.arange(m, dtype=np.int64), m)
    return np.where((gap == 0) | (gap == 1) | (gap == m - 1), -1, partner)


def _run(partner: NDArray[np.int64], pair: tuple[int, int], step: int, room: int) -> int:
    """How many more pairs (k + step·t, j - step·t), t = 1 .. room, continue the run of pair
    (k, j)."""
    k, j = pair
    t = np.arange(1, room + 1, dtype=np.int64)
    m = partner.size
    matches = np.equal(partner[np.remainder(k + step * t, m)], np.remainder(j - step * t, m))
    return room if matches.all() else int(np.argmin(matches))


def _slit(rows: NDArray[np.float64]) -> tuple[int, int, int] | None:
    """A loop's first slit: the first row of its way out, its length in rows, the first row of
    its way back; None when every run leaves a side empty (a spike, or a loop run out and back)."""
    m = rows.shape[0]
    partner = _partners(rows)
    first: list[int] = np.flatnonzero(
        np.greater(partner, np.arange(m, dtype=np.int64))
    ).tolist()  # each pair once
    for k in first:  # rows with a reverse: few
        j = int(partner[k])
        between, beyond = (j - k) % m - 1, (k - j) % m - 1  # rows on either side of the pair
        after = _run(partner, (k, j), 1, between // 2)
        before = _run(partner, (k, j), -1, beyond // 2)
        if between > 2 * after and beyond > 2 * before:
            return (k - before) % m, before + after + 1, (j - after) % m
    return None


def _split(
    rows: NDArray[np.float64], where: str
) -> tuple[list[NDArray[np.int64]], list[Diagnostic]]:
    """A loop's pieces, each as row indices in loop order, sorted by its first row, and a note
    per slit removed."""
    todo: list[NDArray[np.int64]] = [np.arange(rows.shape[0], dtype=np.int64)]
    pieces: list[NDArray[np.int64]] = []
    notes: list[Diagnostic] = []
    while todo:
        index = todo.pop()
        found = _slit(rows[index])
        if found is None:
            pieces.append(index)
            continue
        out, length, back = found
        m = index.size
        inner = (back - out - length) % m  # rows between the way out and the way back
        todo.append(index[(out + length + np.arange(inner)) % m])
        todo.append(index[(back + length + np.arange(m - 2 * length - inner)) % m])
        (x0, y0), (x1, y1) = rows[index[out], 0:2], rows[index[(out + length - 1) % m], 2:4]
        ends = f"({x0:.6g}, {y0:.6g}) to ({x1:.6g}, {y1:.6g})"
        message = f"a zero-width slit from {ends} removed; the loop is split in two"
        notes.append(Diagnostic("LOOP_SLIT", Severity.WARNING, message, where))
    return sorted(pieces, key=lambda p: int(p.min())), notes


def split_slits(loops: CurveRows) -> Slits:
    """Every zero-width slit of every loop removed, its loop split into the loops on either side,
    until none is left. Internal, for the loop tree's screen.

    Implements: REQ-G2D-241.
    """
    rows: list[NDArray[np.float64]] = []
    ids: list[NDArray[np.int64]] = []
    origin: list[int] = []
    notes: list[tuple[int, Diagnostic]] = []
    ends = np.append(loops.row_starts[1:], loops.rows.shape[0])
    for i, (a, b) in enumerate(zip(loops.row_starts.tolist(), ends.tolist(), strict=True)):
        pieces, found = _split(loops.rows[a:b], f"loop {i}")
        rows += [loops.rows[a:b][p] for p in pieces]
        ids += [loops.ids[a:b][p] for p in pieces]
        origin += [i] * len(pieces)
        notes += [(i, note) for note in found]
    sizes = [r.shape[0] for r in rows]
    pieces_rows = CurveRows(
        np.vstack(rows) if rows else np.empty((0, 7)),
        np.concatenate(ids) if ids else np.empty(0, np.int64),
        np.cumsum([0, *sizes[:-1]], dtype=np.int64) if rows else np.empty(0, np.int64),
    )
    return Slits(pieces_rows, np.array(origin, dtype=np.int64), tuple(notes))
