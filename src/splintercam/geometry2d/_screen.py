# SPDX-License-Identifier: Apache-2.0
"""The loop tree's first rules: each loop cleaned, degenerate and thin loops dropped, duplicates
removed (research 01, Loop tree, rules 1 to 3)."""

import dataclasses
import math
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
from ._selfcross import self_contact

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
    diagnostic_loops: tuple[int, ...]  # per diagnostic of the result, the loop it is filed with


@dataclass(frozen=True, slots=True)
class _Candidate:
    index: int
    polyline: NDArray[np.float64]
    area: float
    length: float
    box: NDArray[np.float64]  # x_min, y_min, x_max, y_max


def _covered(a: NDArray[np.float64], b: NDArray[np.float64], t_topo: float) -> bool:
    return _kernels.geometry2d.covered_by(
        a, b, np.zeros(1, np.int64), t_topo
    )  # no point of a farther than t_topo


def _duplicate_of(
    candidate: _Candidate, kept: list[_Candidate], boxes: NDArray[np.float64], ctx: Context
) -> _Candidate | None:
    t_topo = ctx.tolerances.topology_tol_mm
    # Duplicates have boxes within t_topo, eps_len for rounding (DEC-G2D-030).
    slack = t_topo + ctx.tolerances.length_eps_mm
    near = np.flatnonzero((np.abs(boxes - candidate.box) <= slack).all(axis=1))
    for k in near.tolist():
        other = kept[k]
        if _covered(candidate.polyline, other.polyline, t_topo) and _covered(
            other.polyline, candidate.polyline, t_topo
        ):
            return other
    return None


_ONE = np.zeros(1, np.int64)


def _screen_one(
    i: int, points: NDArray[np.float64], rows: CurveRows, ctx: Context
) -> tuple[_Candidate | None, list[Diagnostic], NDArray[np.float64] | None]:
    """Rules 1 and 2 for loop i, with its crossings with itself (REQ-G2D-238) before the area
    tests: the candidate, or None when dropped; its notes; and, when it crosses itself, the
    points where it does (pair (i, i))."""
    where = f"loop {i}"
    t_topo = ctx.tolerances.topology_tol_mm
    cleaned = cleanup(points, ctx)
    notes = [_spike_note(d, points, where) for d in cleaned.diagnostics]
    if cleaned.value is None:  # cleanup always returns the kept indices
        raise RuntimeError(f"cleanup returned no vertices for {where}")
    polyline = points[cleaned.value]
    contact = self_contact(polyline, ctx)
    if contact.kind == "cross":
        message = f"{where} crosses itself, deeper than t_topo"
        return (
            None,
            [*notes, Diagnostic("LOOPS_CROSS", Severity.ERROR, message, where)],
            contact.nodes,
        )
    if contact.kind == "degenerate":
        message = f"{where} touches itself everywhere: every cycle lies within t_topo of the others"
        return None, [*notes, Diagnostic("LOOP_DEGENERATE", Severity.WARNING, message, where)], None
    area_test = signed_area(rows, ctx)
    if area_test.value is None:
        return (
            None,
            [*notes, *(dataclasses.replace(d, location=where) for d in area_test.diagnostics)],
            None,
        )
    area, length = polygon_area_length(polyline)
    if abs(area) <= _THINNESS_FACTOR * t_topo * length:
        message = f"|A| = {abs(area):.3g} mm² of its flattening is at most 1.5·t_topo·L"
        return None, [*notes, Diagnostic("LOOP_DEGENERATE", Severity.WARNING, message, where)], None
    if contact.kind == "touch":
        area = math.copysign(abs(area), contact.sign)  # the sign of its depth-0 cycles
    box = np.concatenate([polyline.min(axis=0), polyline.max(axis=0)])
    return _Candidate(i, polyline, area, length, box), notes, None


def _all_crossings(
    self_points: list[tuple[int, NDArray[np.float64]]],
    pair_points: NDArray[np.float64],
    pair_loops: NDArray[np.int64],
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    """Every crossing point with its loop pair, sorted by the pair, then x, then y (REQ-G2D-236);
    a loop crossing itself is the pair (i, i)."""
    points = [pair_points, *(nodes for _, nodes in self_points)]
    pairs = [pair_loops, *(np.full((nodes.shape[0], 2), i, np.int64) for i, nodes in self_points)]
    all_points = np.vstack(points).reshape(-1, 2)
    all_pairs = np.vstack(pairs).reshape(-1, 2)
    order = np.lexsort((all_points[:, 1], all_points[:, 0], all_pairs[:, 1], all_pairs[:, 0]))
    return all_points[order], all_pairs[order]


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
    self_points: list[tuple[int, NDArray[np.float64]]] = []
    for i, (points, rows, ids) in enumerate(pieces):
        candidate, loop_notes, crossing = _screen_one(i, points, CurveRows(rows, ids, _ONE), ctx)
        notes += [(i, note) for note in loop_notes]
        if crossing is not None:
            self_points.append((i, crossing))
        if candidate is None:
            continue
        boxes = np.array([c.box for c in kept]).reshape(-1, 4)
        original = _duplicate_of(candidate, kept, boxes, ctx)
        if original is not None:
            message = f"loop {i} duplicates loop {original.index} within t_topo; removed"
            location = f"loops {original.index} and {i}"
            notes.append((i, Diagnostic("LOOP_DUPLICATE", Severity.WARNING, message, location)))
            continue
        kept.append(candidate)
    pair_points, pair_loops, crossing_notes = find_crossings(
        [c.index for c in kept], [c.polyline for c in kept], t_topo
    )
    notes += crossing_notes
    crossing_points, crossing_loops = _all_crossings(self_points, pair_points, pair_loops)
    screened = Screened(
        kept=np.array([c.index for c in kept], dtype=np.int64),
        polylines=tuple(c.polyline for c in kept),
        areas=np.array([c.area for c in kept], dtype=np.float64),
        lengths=np.array([c.length for c in kept], dtype=np.float64),
        crossing_points=crossing_points,
        crossing_loops=crossing_loops,
        diagnostic_loops=(),
    )
    ordered = sorted(notes, key=lambda pair: pair[0])  # stable
    screened = dataclasses.replace(screened, diagnostic_loops=tuple(k for k, _ in ordered))
    return Result(screened, tuple(note for _, note in ordered))
