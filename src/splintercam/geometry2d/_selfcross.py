# SPDX-License-Identifier: Apache-2.0
"""A loop's crossings with itself (research 01, Loop tree, rule 4; REQ-G2D-238): resolved into
touching cycles, slivers within t_topo dropped, the rest nested; the loop crosses itself when
their winding leaves 0 and 1."""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context

from ._area import polygon_area_length
from ._contain import nest
from ._rows import CurveRows

_SIMPLE, _CYCLES, _OVERLAP = 0, 1, 2  # SelfContact in kernel/selfcross.hpp


@dataclass(frozen=True, slots=True)
class SelfContact:
    """`simple` (no self-contact), `touch` (the loop touches itself; `sign` is its depth-0
    cycles'), `cross`, or `degenerate` (every cycle a sliver); `nodes` where it meets itself."""

    kind: Literal["simple", "touch", "cross", "degenerate"]
    sign: float
    nodes: NDArray[np.float64]


def _cycles(
    loop: NDArray[np.float64],
) -> tuple[int, list[NDArray[np.float64]], NDArray[np.int64], NDArray[np.float64]]:
    kernel = _kernels.geometry2d
    room = 4 * loop.shape[0] + 8
    while True:
        points, cycles, nodes = (
            np.empty((room, 2)),
            np.empty((room, 2), np.int64),
            np.empty((room, 2)),
        )
        status, n_points, n_cycles, n_nodes = kernel.self_cycles(loop, points, cycles, nodes)
        if max(n_points, n_cycles, n_nodes) <= room:
            break
        room = max(n_points, n_cycles, n_nodes)
    starts, first = cycles[:n_cycles, 0], cycles[:n_cycles, 1].copy()
    ends = [*starts[1:].tolist(), n_points] if n_cycles else []
    found = [points[a:b].copy() for a, b in zip(starts.tolist(), ends, strict=True)]
    return status, found, first, nodes[:n_nodes].copy()


def _covered(a: NDArray[np.float64], others: list[NDArray[np.float64]], t_topo: float) -> bool:
    if not others:
        return False
    starts = np.cumsum([0] + [o.shape[0] for o in others[:-1]], dtype=np.int64)
    return _kernels.geometry2d.covered_by(a, np.vstack(others), starts, t_topo)


def _rows(polyline: NDArray[np.float64]) -> CurveRows:
    n = polyline.shape[0]
    rows = np.hstack(
        [polyline, np.roll(polyline, -1, axis=0), np.full((n, 2), math.nan), np.zeros((n, 1))]
    )
    return CurveRows(rows, np.arange(n, dtype=np.int64), np.zeros(1, np.int64))


def _kept(cycles: list[NDArray[np.float64]], signs: list[float], t_topo: float) -> list[int]:
    """The cycles not within t_topo of the others; of two that cover each other, both go when
    their signs differ and both stay when they agree (REQ-G2D-238)."""
    flagged = [_covered(c, cycles[:k] + cycles[k + 1 :], t_topo) for k, c in enumerate(cycles)]
    keep: list[int] = []
    for k, c in enumerate(cycles):
        if not flagged[k]:
            keep.append(k)
            continue
        unflagged = [cycles[j] for j in range(len(cycles)) if j != k and not flagged[j]]
        if _covered(c, unflagged, t_topo):
            continue  # a sliver along the other cycles
        partners = [
            j
            for j in range(len(cycles))
            if j != k
            and flagged[j]
            and _covered(c, [cycles[j]], t_topo)
            and _covered(cycles[j], [c], t_topo)
        ]
        if not partners or any(signs[j] == signs[k] for j in partners):
            keep.append(k)
    return keep


def self_contact(loop: NDArray[np.float64], ctx: Context) -> SelfContact:
    """Whether a cleaned topology flattening crosses or touches itself, by the Seifert resolution
    of REQ-G2D-238. A stretch run twice, or two ends leaving a point in one direction, counts as a
    crossing, provisionally (DEC-G2D-033).

    Implements: REQ-G2D-160 (a loop with itself), REQ-G2D-238.
    """
    t_topo = ctx.tolerances.topology_tol_mm
    status, cycles, first, nodes = _cycles(loop)
    if status == _SIMPLE:
        return SelfContact("simple", 0.0, nodes)
    if status == _OVERLAP:
        return SelfContact("cross", 0.0, nodes)
    measures = [polygon_area_length(c) for c in cycles]
    signs = [math.copysign(1.0, area) for area, _ in measures]
    keep = _kept(cycles, signs, t_topo)
    if not keep:
        return SelfContact("degenerate", 0.0, nodes)
    order = sorted(keep, key=lambda k: int(first[k]))  # input order: the cycle's first edge
    polylines = [cycles[k] for k in order]
    areas = np.array([measures[k][0] for k in order])
    lengths = np.array([measures[k][1] for k in order])
    parents, crossing = nest(polylines, areas, lengths, [_rows(p) for p in polylines], ctx)
    if crossing:
        return SelfContact("cross", 0.0, nodes)
    roots = {math.copysign(1.0, areas[k]) for k, p in enumerate(parents) if p < 0}
    alternates = all(
        math.copysign(1.0, areas[k]) != math.copysign(1.0, areas[p])
        for k, p in enumerate(parents)
        if p >= 0
    )
    if len(roots) > 1 or not alternates:
        return SelfContact("cross", 0.0, nodes)
    return SelfContact("touch", roots.pop(), nodes)
