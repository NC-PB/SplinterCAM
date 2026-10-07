# SPDX-License-Identifier: Apache-2.0
"""The loop tree's first rules: each loop cleaned, degenerate and thin loops dropped, duplicates
removed (research 01, Loop tree, rules 1 to 3)."""

import dataclasses
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._area import polygon_area_length, signed_area
from ._cleanup import cleanup
from ._crossings import find_crossings
from ._loops import topology_flattening
from ._rows import CurveRows

# Rule 2: a loop whose topology flattening has |A| <= 1.5·t_topo·L, thinner than about 3·t_topo on
# average, is dropped (research 01, Loop tree, rule 2). A rule of the research, not a tuning share.
_THINNESS_FACTOR = 1.5


def _spike_note(diagnostic: Diagnostic, points: NDArray[np.float64], where: str) -> Diagnostic:
    """`cleanup`'s spike, located by its loop and named by its point (REQ-G2D-236)."""
    vertex = int((diagnostic.location or "vertex 0").split()[-1])
    x, y = points[vertex].tolist()
    message = f"{diagnostic.message} at ({x:.6g}, {y:.6g})"
    return dataclasses.replace(diagnostic, message=message, location=where)


@dataclass(frozen=True, slots=True)
class Screened:
    """The loops that survive rules 1 to 3: `kept` their input indices, ascending; per kept loop
    its cleaned topology flattening ((n, 2), as given, not yet normalised) and that polyline's
    signed area and length; the crossings among the kept loops (rule 4)."""

    kept: NDArray[np.int64]
    polylines: tuple[NDArray[np.float64], ...]
    areas: NDArray[np.float64]
    lengths: NDArray[np.float64]
    crossing_points: NDArray[np.float64]
    crossing_loops: NDArray[np.int64]


@dataclass(frozen=True, slots=True)
class _Candidate:
    index: int
    polyline: NDArray[np.float64]
    area: float
    length: float


def _covered(a: NDArray[np.float64], b: NDArray[np.float64], t_topo: float) -> bool:
    inside, outside = _kernels.geometry2d.crossing_depth(a, b, t_topo)
    return not (inside or outside)  # no point of a farther than t_topo from b


def _duplicate_of(
    candidate: _Candidate, kept: list[_Candidate], boxes: NDArray[np.float64], ctx: Context
) -> _Candidate | None:
    t_topo = ctx.tolerances.topology_tol_mm
    # Loops within t_topo of each other both ways have boxes within t_topo of each other; eps_len
    # absorbs the rounding of the cover (DEC-G2D-030).
    box = np.concatenate([candidate.polyline.min(axis=0), candidate.polyline.max(axis=0)])
    near = np.flatnonzero(
        (np.abs(boxes - box) <= t_topo + ctx.tolerances.length_eps_mm).all(axis=1)
    )
    for k in near.tolist():
        other = kept[k]
        if _covered(candidate.polyline, other.polyline, t_topo) and _covered(
            other.polyline, candidate.polyline, t_topo
        ):
            return other
    return None


def screen_loops(loops: CurveRows, ctx: Context) -> Result[Screened]:
    """Rules 1 to 3 of the loop tree on the loops' topology flattenings, in this order: cleanup
    (spikes reported), the area test of REQ-G2D-133, the thinness test |A| <= 1.5·t_topo·L, and
    duplicates (each loop against the kept loops before it in input order, the earlier kept).
    Diagnostics name the input loops and follow input-loop order. Internal (SPEC, Public
    interface).

    Implements: REQ-G2D-154 to 161, REQ-G2D-163, REQ-G2D-236, REQ-G2D-237.
    """
    t_topo = ctx.tolerances.topology_tol_mm
    topology = topology_flattening(loops, ctx)
    pieces = zip(
        np.split(topology.points, topology.loop_starts[1:]),
        np.split(loops.rows, loops.row_starts[1:]),
        np.split(loops.ids, loops.row_starts[1:]),
        strict=True,
    )
    notes: list[tuple[int, Diagnostic]] = []
    kept: list[_Candidate] = []
    for i, (points, rows, ids) in enumerate(pieces):
        where = f"loop {i}"
        cleaned = cleanup(points, ctx)
        notes += [(i, _spike_note(d, points, where)) for d in cleaned.diagnostics]
        if cleaned.value is None:  # cleanup always returns the kept indices
            raise RuntimeError(f"cleanup returned no vertices for {where}")
        area_test = signed_area(CurveRows(rows, ids, np.zeros(1, np.int64)), ctx)
        if area_test.value is None:
            notes += [(i, dataclasses.replace(d, location=where)) for d in area_test.diagnostics]
            continue
        polyline = points[cleaned.value]
        area, length = polygon_area_length(polyline)
        if abs(area) <= _THINNESS_FACTOR * t_topo * length:
            message = f"|A| = {abs(area):.3g} mm² of its flattening is at most 1.5·t_topo·L"
            notes.append((i, Diagnostic("LOOP_DEGENERATE", Severity.WARNING, message, where)))
            continue
        candidate = _Candidate(i, polyline, area, length)
        boxes = np.array([[*c.polyline.min(axis=0), *c.polyline.max(axis=0)] for c in kept])
        original = _duplicate_of(candidate, kept, boxes.reshape(-1, 4), ctx)
        if original is not None:
            message = f"loop {i} duplicates loop {original.index} within t_topo; removed"
            location = f"loops {original.index} and {i}"
            notes.append((i, Diagnostic("LOOP_DUPLICATE", Severity.WARNING, message, location)))
            continue
        kept.append(candidate)
    crossing_points, crossing_loops, crossing_notes = find_crossings(
        [c.index for c in kept], [c.polyline for c in kept], t_topo
    )
    notes += crossing_notes
    screened = Screened(
        kept=np.array([c.index for c in kept], dtype=np.int64),
        polylines=tuple(c.polyline for c in kept),
        areas=np.array([c.area for c in kept], dtype=np.float64),
        lengths=np.array([c.length for c in kept], dtype=np.float64),
        crossing_points=crossing_points,
        crossing_loops=crossing_loops,
    )
    ordered = [note for _, note in sorted(notes, key=lambda pair: pair[0])]  # stable
    return Result(screened, tuple(ordered))
