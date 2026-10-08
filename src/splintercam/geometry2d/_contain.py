# SPDX-License-Identifier: Apache-2.0
"""Containment of one loop in another by probes, and the nesting of a set of loops (research 01,
Loop tree, rule 5)."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import Context

from ._distances import polyline_distances
from ._region import PointLocation, point_in_region
from ._rows import CurveRows

_ONE_LOOP = np.zeros(1, np.int64)


@dataclass(frozen=True, slots=True)
class Containment:
    """Whether B lies in A, and whether a probe decided it (else the rule 5 fallback would)."""

    contained: bool
    by_probe: bool


def _projections(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """Each vertex of a projected onto the nearest segment of closed polyline b (rule 5)."""
    start, d = b, np.roll(b, -1, axis=0) - b
    t = np.clip(((a[:, None, :] - start) * d).sum(axis=2) / (d * d).sum(axis=1), 0.0, 1.0)
    feet = start + t[..., None] * d
    nearest = np.argmin(((a[:, None, :] - feet) ** 2).sum(axis=2), axis=1)  # lowest index on ties
    return feet[np.arange(a.shape[0]), nearest]


def contains(
    b: NDArray[np.float64], a: NDArray[np.float64], a_rows: CurveRows, ctx: Context
) -> Containment:
    """B ⊂ A by the first probe of B farther than t_topo from A's flattening, among B's vertices,
    the midpoints of its segments and the projections of A's vertices onto B (REQ-G2D-168),
    located against A's exact rows alone (REQ-G2D-153, 167). Without such a probe the answer is
    "not contained", provisional until the rule 5 fallback (DEC-G2D-032).
    """
    t_topo = ctx.tolerances.topology_tol_mm
    groups = (b, (b + np.roll(b, -1, axis=0)) / 2, None)
    for group in groups:
        candidates = _projections(a, b) if group is None else group
        far = np.flatnonzero(np.isinf(polyline_distances(candidates, a, _ONE_LOOP, t_topo)))
        if far.size > 0:
            location = point_in_region(candidates[far[:1]], a_rows, ctx)[0]
            return Containment(bool(location == PointLocation.IN), True)
    return Containment(False, False)


Decision = Literal["a in b", "b in a", "apart", "cross"]


def both_ways(a_in_b: Containment, b_in_a: Containment) -> Decision:
    """The containment of two loops tested both ways (REQ-G2D-166): a probe's result stands over
    the fallback's (REQ-G2D-170); two probes finding each in the other mean the loops cross
    (REQ-G2D-173)."""
    if a_in_b.contained and b_in_a.contained:
        if a_in_b.by_probe and b_in_a.by_probe:
            return "cross"
        return "a in b" if a_in_b.by_probe else "b in a"
    if a_in_b.contained:
        return "a in b"
    return "b in a" if b_in_a.contained else "apart"


def nest(
    polylines: list[NDArray[np.float64]],
    areas: NDArray[np.float64],
    lengths: NDArray[np.float64],
    rows: list[CurveRows],
    ctx: Context,
) -> tuple[list[int], list[tuple[int, int]]]:
    """Per loop its parent, the smallest loop containing it (-1 for none, the lower index on a
    tie), and the pairs that contain each other by two probes (REQ-G2D-164 to 166, 173). Only
    loops whose boxes overlap are tested; one way when their areas differ by more than
    t_topo·(L_A + L_B), both ways otherwise."""
    t_topo = ctx.tolerances.topology_tol_mm
    size = np.abs(areas)
    boxes = np.array([[*p.min(axis=0), *p.max(axis=0)] for p in polylines]).reshape(-1, 4)
    containers: list[list[int]] = [[] for _ in polylines]
    crossing: list[tuple[int, int]] = []
    for a in range(len(polylines)):
        for b in range(a + 1, len(polylines)):
            if np.any(boxes[a, :2] > boxes[b, 2:]) or np.any(boxes[b, :2] > boxes[a, 2:]):
                continue

            def inside(inner: int, outer: int) -> Containment:
                return contains(polylines[inner], polylines[outer], rows[outer], ctx)

            if abs(size[a] - size[b]) <= t_topo * (lengths[a] + lengths[b]):
                decision = both_ways(inside(a, b), inside(b, a))
            elif size[a] > size[b]:
                decision = "b in a" if inside(b, a).contained else "apart"
            else:
                decision = "a in b" if inside(a, b).contained else "apart"
            if decision == "a in b":
                containers[a].append(b)
            elif decision == "b in a":
                containers[b].append(a)
            elif decision == "cross":
                crossing.append((a, b))
    parents = [min(c, key=lambda k: (size[k], k)) if c else -1 for c in containers]
    return parents, crossing
