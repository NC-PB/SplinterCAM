# SPDX-License-Identifier: Apache-2.0
"""Containment of one loop in another by probes, and the nesting of a set of loops (research 01,
Loop tree, rule 5)."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context

from ._distances import polyline_distances
from ._grid import MAX_SPAN_GRID_UNITS
from ._region import PointLocation, point_in_region
from ._rows import CurveRows

_ONE_LOOP = np.zeros(1, np.int64)
_CHUNK_PAIRS = 1 << 20  # vertex-segment pairs per NumPy chunk: memory, not a tolerance


@dataclass(frozen=True, slots=True)
class Containment:
    """Whether B lies in A; whether a probe decided it, else the rule 5 fallback with the area of
    B minus A in mm²; and the code of a grid call that was refused or failed."""

    contained: bool
    by_probe: bool
    difference_mm2: float = 0.0
    refused: str | None = None


def _projections(a: NDArray[np.float64], b: NDArray[np.float64]) -> NDArray[np.float64]:
    """Each vertex of a projected onto the nearest segment of closed polyline b (rule 5)."""
    start, d = b, np.roll(b, -1, axis=0) - b
    found: list[NDArray[np.float64]] = []
    for chunk in np.array_split(a, max(1, a.shape[0] * b.shape[0] // _CHUNK_PAIRS)):
        t = np.clip(((chunk[:, None, :] - start) * d).sum(axis=2) / (d * d).sum(axis=1), 0.0, 1.0)
        feet = start + t[..., None] * d
        nearest = np.argmin(((chunk[:, None, :] - feet) ** 2).sum(axis=2), axis=1)  # lowest first
        found.append(feet[np.arange(chunk.shape[0]), nearest])
    return np.vstack(found) if found else np.empty((0, 2))


def contains(
    b: NDArray[np.float64], a: NDArray[np.float64], a_rows: CurveRows, ctx: Context
) -> Containment:
    """B ⊂ A by the first probe of B farther than t_topo from A's flattening, among B's vertices,
    the midpoints of its segments and the projections of A's vertices onto B (REQ-G2D-168),
    located against A's exact rows alone (REQ-G2D-153, 167). Without such a probe the grid decides
    (the rule 5 fallback, REQ-G2D-169; DEC-G2D-035).
    """
    t_topo = ctx.tolerances.topology_tol_mm
    groups = (b, (b + np.roll(b, -1, axis=0)) / 2, None)
    for group in groups:
        candidates = _projections(a, b) if group is None else group
        far = np.flatnonzero(np.isinf(polyline_distances(candidates, a, _ONE_LOOP, t_topo)))
        locations = point_in_region(candidates[far], a_rows, ctx)
        # ON can only be a part of A that cleanup removed, a spike: the next probe decides.
        decided = np.flatnonzero(locations != PointLocation.ON)
        if decided.size > 0:
            return Containment(bool(locations[decided[0]] == PointLocation.IN), True)
    return _fallback(b, a, ctx)


def _fallback(b: NDArray[np.float64], a: NDArray[np.float64], ctx: Context) -> Containment:
    """B ⊂ A when the area of B minus A, from Clipper2's NonZero difference on the grid, is less
    than half of B's grid area (REQ-G2D-169)."""
    u = ctx.tolerances.grid_unit_mm
    status, difference, area_b = _kernels.geometry2d.grid_difference(b, a, u, MAX_SPAN_GRID_UNITS)
    if status != 0:
        refused = "REGION_TOO_LARGE" if status == 1 else "REGION_FAILED"
        return Containment(False, False, refused=refused)
    return Containment(difference < area_b / 2, False, difference)


Decision = Literal["a in b", "b in a", "apart", "cross", "refused"]


def both_ways(a_in_b: Containment, b_in_a: Containment) -> Decision:
    """The containment of two loops tested both ways (REQ-G2D-166), a preceding b in input order:
    a probe's result stands over the fallback's (REQ-G2D-170); two fallback results go to the
    smaller difference, then to the earlier loop (REQ-G2D-171, 172); two probes finding each in the
    other mean the loops cross (REQ-G2D-173)."""
    if a_in_b.refused or b_in_a.refused:
        return "refused"
    if a_in_b.contained and b_in_a.contained:
        if a_in_b.by_probe and b_in_a.by_probe:
            return "cross"
        if a_in_b.by_probe != b_in_a.by_probe:
            return "a in b" if a_in_b.by_probe else "b in a"
        # Two fallback results: the smaller difference is the inner loop, a on equality, since a
        # precedes b in input order (REQ-G2D-171, 172).
        return "a in b" if a_in_b.difference_mm2 <= b_in_a.difference_mm2 else "b in a"
    if a_in_b.contained:
        return "a in b"
    return "b in a" if b_in_a.contained else "apart"


@dataclass(frozen=True, slots=True)
class Nesting:
    """Per loop its parent (-1 for none) and depth; the pairs that cross or do not nest; the
    pairs whose fallback the grid refused or failed, with the code."""

    parents: list[int]
    depths: list[int]
    crossing: list[tuple[int, int]]
    refused: list[tuple[int, int, str]]


# A direction `nest` does not test: as a probe finding "not contained", so `both_ways` decides
# from the other direction alone.
_UNTESTED = Containment(False, True)


def nest(
    polylines: list[NDArray[np.float64]],
    areas: NDArray[np.float64],
    lengths: NDArray[np.float64],
    rows: list[CurveRows],
    ctx: Context,
) -> Nesting:
    """Per loop its parent and depth, its number of containers (REQ-G2D-164 to 166, 169 to 174).
    Only loops whose boxes overlap are tested; one way when their areas differ by more than
    t_topo·(L_A + L_B), both ways otherwise."""
    t_topo = ctx.tolerances.topology_tol_mm
    size = np.abs(areas)
    boxes = np.array([[*p.min(axis=0), *p.max(axis=0)] for p in polylines]).reshape(-1, 4)
    containers: list[list[int]] = [[] for _ in polylines]
    crossing: list[tuple[int, int]] = []
    refused: list[tuple[int, int, str]] = []
    for a, b in overlapping_pairs(boxes):
        close = abs(size[a] - size[b]) <= t_topo * (lengths[a] + lengths[b])
        # Both ways when the areas are close, else only the smaller in the larger (REQ-G2D-165).
        a_in_b = _UNTESTED
        if close or size[a] < size[b]:
            a_in_b = contains(polylines[a], polylines[b], rows[b], ctx)
        b_in_a = _UNTESTED
        if close or size[a] > size[b]:
            b_in_a = contains(polylines[b], polylines[a], rows[a], ctx)
        decision = both_ways(a_in_b, b_in_a)
        if decision == "a in b":
            containers[a].append(b)
        elif decision == "b in a":
            containers[b].append(a)
        elif decision == "cross":
            crossing.append((a, b))
        elif decision == "refused":
            refused.append((a, b, a_in_b.refused or b_in_a.refused or "REGION_FAILED"))
    parents, unnested = _parents(containers)
    return Nesting(parents, [len(c) for c in containers], sorted({*crossing, *unnested}), refused)


def _parents(containers: list[list[int]]) -> tuple[list[int], list[tuple[int, int]]]:
    """The parent of each loop: the container whose own containers are all the others
    (REQ-G2D-164). Without one the containment is no nesting (a cycle, or two containers beside
    each other), and the loop and its first container are reported as crossing (DEC-G2D-032)."""
    parents: list[int] = []
    unnested: list[tuple[int, int]] = []
    for k, mine in enumerate(containers):
        inner = [p for p in mine if set(containers[p]) == set(mine) - {p}]
        if mine and not inner:
            unnested.append((min(k, mine[0]), max(k, mine[0])))
        parents.append(inner[0] if inner else -1)
    return parents, unnested


def overlapping_pairs(boxes: NDArray[np.float64]) -> list[tuple[int, int]]:
    """The pairs (a < b) of (k, 4) boxes [x_min, y_min, x_max, y_max] that overlap or touch, in
    order, from one broadcast comparison (the pair loops of rules 4 and 5)."""
    low, high = boxes[:, :2], boxes[:, 2:]
    apart = (low[:, None] > high[None]).any(axis=2) | (low[None] > high[:, None]).any(axis=2)
    a, b = np.nonzero(np.triu(~apart, k=1))
    return list(zip(a.tolist(), b.tolist(), strict=True))


def contained_by_difference(b: CurveRows, a: CurveRows, ctx: Context) -> tuple[bool, float]:
    """The rule 5 fallback alone on two single loops' topology flattenings: B ⊂ A, and the area
    of B minus A in mm² (internal, for tests; REQ-G2D-169). A refused or failed grid call is a
    `ValueError` here; the loop tree reports it as a diagnostic."""
    from ._loops import topology_flattening

    result = _fallback(topology_flattening(b, ctx).points, topology_flattening(a, ctx).points, ctx)
    if result.refused:
        raise ValueError(f"the grid refused the fallback: {result.refused}")
    return result.contained, result.difference_mm2


def fallback_inner(a: CurveRows, b: CurveRows, ctx: Context) -> int:
    """The tie of two fallback results, a preceding b in input order: 0 when a is the inner loop,
    1 when b (internal, for tests; REQ-G2D-171, 172)."""
    return (
        0 if contained_by_difference(a, b, ctx)[1] <= contained_by_difference(b, a, ctx)[1] else 1
    )
