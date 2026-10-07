# SPDX-License-Identifier: Apache-2.0
"""Crossings between loops (research 01, Loop tree, rule 4): two loops cross when one reaches more
than t_topo into the other on both sides; otherwise they touch."""

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Diagnostic, Severity


def contact_points(
    a: NDArray[np.float64], b: NDArray[np.float64], limit_mm: float
) -> NDArray[np.float64]:
    """Where closed polylines a and b meet, by exact signs, sorted by x, then y (REQ-G2D-160).
    `limit_mm` (> 0) sizes the kernel's search grid only. Internal (SPEC, internal entries)."""
    kernel = _kernels.geometry2d
    out = np.empty((a.shape[0] + b.shape[0], 2), dtype=np.float64)
    count = kernel.contact_points(a, b, limit_mm, out)
    if count > out.shape[0]:  # more contacts than vertices: ask again with room for all
        out = np.empty((count, 2), dtype=np.float64)
        kernel.contact_points(a, b, limit_mm, out)
    found = out[:count]
    found.flags.writeable = False
    return found


def _reaches_through(a: NDArray[np.float64], b: NDArray[np.float64], t_topo: float) -> bool:
    inside, outside = _kernels.geometry2d.crossing_depth(a, b, t_topo)
    return inside and outside


def find_crossings(
    indices: list[int], polylines: list[NDArray[np.float64]], t_topo: float
) -> tuple[NDArray[np.float64], NDArray[np.int64], list[tuple[int, Diagnostic]]]:
    """The crossing pairs among the loops (input `indices`, their cleaned topology flattenings):
    their contact points sorted by loop pair, then x, then y, the pair of input indices per
    point (lower first), and one `LOOPS_CROSS` (error) per pair keyed by its lower index.

    Implements: REQ-G2D-160, REQ-G2D-161, REQ-G2D-163, REQ-G2D-237.
    """
    boxes = [(p.min(axis=0), p.max(axis=0)) for p in polylines]
    points: list[NDArray[np.float64]] = []
    pairs: list[tuple[int, int]] = []
    notes: list[tuple[int, Diagnostic]] = []
    for a in range(len(polylines)):
        for b in range(a + 1, len(polylines)):
            (low_a, high_a), (low_b, high_b) = boxes[a], boxes[b]
            if np.any(low_a > high_b) or np.any(low_b > high_a):
                continue
            pa, pb = polylines[a], polylines[b]
            if not (_reaches_through(pa, pb, t_topo) or _reaches_through(pb, pa, t_topo)):
                continue  # they touch at most (REQ-G2D-163)
            found = contact_points(pa, pb, t_topo)
            i, j = indices[a], indices[b]
            points.append(found)
            pairs += [(i, j)] * found.shape[0]
            message = f"loops {i} and {j} cross at {found.shape[0]} points, deeper than t_topo"
            notes.append(
                (i, Diagnostic("LOOPS_CROSS", Severity.ERROR, message, f"loops {i} and {j}"))
            )
    crossing_points = np.vstack(points) if points else np.empty((0, 2), dtype=np.float64)
    crossing_loops = np.array(pairs, dtype=np.int64).reshape(-1, 2)
    return crossing_points, crossing_loops, notes
