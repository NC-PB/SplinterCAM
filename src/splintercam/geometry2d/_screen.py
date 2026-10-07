# SPDX-License-Identifier: Apache-2.0
"""The loop tree's first rules: each loop cleaned, degenerate and thin loops dropped, duplicates
removed (research 01, Loop tree, rules 1 to 3)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._area import polygon_area_length, signed_area
from ._cleanup import cleanup
from ._distances import polyline_distances
from ._loops import topology_flattening
from ._rows import CurveRows

# Rule 2: a loop whose topology flattening has |A| <= 1.5·t_topo·L, thinner than about 3·t_topo on
# average, is dropped (research 01, Loop tree, rule 2). A rule of the research, not a tuning share.
_THINNESS_FACTOR = 1.5


@dataclass(frozen=True, slots=True)
class Screened:
    """The loops that survive rules 1 to 3: `kept` their input indices, ascending; per kept loop
    its cleaned topology flattening ((n, 2), as given, not yet normalised) and that polyline's
    signed area and length."""

    kept: NDArray[np.int64]
    polylines: tuple[NDArray[np.float64], ...]
    areas: NDArray[np.float64]
    lengths: NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class _Candidate:
    index: int
    polyline: NDArray[np.float64]
    area: float
    length: float


def _located(diagnostic: Diagnostic, location: str) -> Diagnostic:
    return Diagnostic(diagnostic.code, diagnostic.severity, diagnostic.message, location)


def _one_loop(loops: CurveRows, i: int) -> CurveRows:
    first = int(loops.row_starts[i])
    end = int(loops.row_starts[i + 1]) if i + 1 < loops.row_starts.size else loops.rows.shape[0]
    return CurveRows(loops.rows[first:end], loops.ids[first:end], np.zeros(1, np.int64))


def _within(a: NDArray[np.float64], b: NDArray[np.float64], t_topo: float) -> bool:
    """Every vertex of polyline a lies within t_topo of polyline b."""
    distances = polyline_distances(a, b, np.zeros(1, np.int64), t_topo)
    return bool(np.isfinite(distances).all())


def _duplicate_of(
    candidate: _Candidate, kept: list[_Candidate], t_topo: float
) -> _Candidate | None:
    """The first kept loop the candidate duplicates (rule 3), comparing only loops whose bounding
    boxes come within t_topo of each other."""
    low, high = candidate.polyline.min(axis=0), candidate.polyline.max(axis=0)
    for other in kept:
        other_low, other_high = other.polyline.min(axis=0), other.polyline.max(axis=0)
        if np.any(other_low > high + t_topo) or np.any(low > other_high + t_topo):
            continue
        if _within(candidate.polyline, other.polyline, t_topo) and _within(
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

    Implements: REQ-G2D-154 to 159, REQ-G2D-236.
    """
    t_topo = ctx.tolerances.topology_tol_mm
    topology = topology_flattening(loops, ctx)
    ends = np.append(topology.loop_starts[1:], topology.points.shape[0])
    notes: list[tuple[int, Diagnostic]] = []
    kept: list[_Candidate] = []
    for i, (start, end) in enumerate(
        zip(topology.loop_starts.tolist(), ends.tolist(), strict=True)
    ):
        where = f"loop {i}"
        cleaned = cleanup(topology.points[start:end], ctx)
        notes += [(i, _located(d, where)) for d in cleaned.diagnostics]
        if cleaned.value is None:  # cleanup always returns the kept indices
            raise RuntimeError(f"cleanup returned no vertices for {where}")
        area_test = signed_area(_one_loop(loops, i), ctx)
        if area_test.value is None:
            notes += [(i, _located(d, where)) for d in area_test.diagnostics]
            continue
        polyline = topology.points[start:end][cleaned.value]
        area, length = polygon_area_length(polyline)
        if abs(area) <= _THINNESS_FACTOR * t_topo * length:
            message = f"|A| = {abs(area):.3g} mm² of its flattening is at most 1.5·t_topo·L"
            notes.append((i, Diagnostic("LOOP_DEGENERATE", Severity.WARNING, message, where)))
            continue
        candidate = _Candidate(i, polyline, area, length)
        original = _duplicate_of(candidate, kept, t_topo)
        if original is not None:
            message = f"loop {i} duplicates loop {original.index} within t_topo; removed"
            location = f"loops {original.index} and {i}"
            notes.append((i, Diagnostic("LOOP_DUPLICATE", Severity.WARNING, message, location)))
            continue
        kept.append(candidate)
    screened = Screened(
        kept=np.array([c.index for c in kept], dtype=np.int64),
        polylines=tuple(c.polyline for c in kept),
        areas=np.array([c.area for c in kept], dtype=np.float64),
        lengths=np.array([c.length for c in kept], dtype=np.float64),
    )
    ordered = [note for _, note in sorted(notes, key=lambda pair: pair[0])]  # stable
    return Result(screened, tuple(ordered))
