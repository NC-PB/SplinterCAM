# SPDX-License-Identifier: Apache-2.0
"""The loop tree's type and the side-correct flattening of its loops (research 01, Loop tree and
Flattening with a known error side)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import TOLERANCE_DEFAULTS, Context

from ._polygon import MIN_LOOP_VERTICES as _MIN_LOOP_VERTICES
from ._polygon import FlatRegion, PolygonRegion, RegionKind
from ._rows import CurveRows

# π/2, a declared parameter (REQ-G2D-230), passed to the kernel as a plain value, as in _flatten.py.
_MAX_STEP_RAD = TOLERANCE_DEFAULTS["flatten_step_max_rad"].default


@dataclass(frozen=True, slots=True)
class LoopTree:
    """Closed loops checked and nested: `loops` the kept loops, normalised (even depth CCW, odd
    depth CW, the inside on the left), in input order; per loop its `parent` (index into loops,
    -1 for none), `depth` and `input_index`; `crossing_points` (c, 2) and `crossing_loops` (c, 2),
    the crossings of `LOOPS_CROSS` and their input loops. One built directly is unchecked.
    """

    loops: CurveRows
    parent: NDArray[np.int64]
    depth: NDArray[np.int64]
    input_index: NDArray[np.int64]
    crossing_points: NDArray[np.float64]
    crossing_loops: NDArray[np.int64]


def _vertex_counts(loops: CurveRows, flags: NDArray[np.uint8], t_mm: float) -> NDArray[np.int64]:
    """Per row the vertices it adds to its flattened loop (DEC-G2D-028)."""
    rows = loops.rows
    counts = np.empty(rows.shape[0], dtype=np.int64)
    _kernels.geometry2d.row_vertex_counts(rows, flags, t_mm, _MAX_STEP_RAD, counts)
    if np.any(counts < 0):
        raise ValueError(f"t_mm {t_mm!r} needs more steps than an int holds")
    # A row that ends where it starts, other than a full circle, adds no vertex (REQ-G2D-185).
    empty = (rows[:, 0:2] == rows[:, 2:4]).all(axis=1) & (np.abs(rows[:, 6]) <= np.pi)
    counts[empty] = 0
    # In a loop that would keep fewer than 3 vertices, an inscribed arc takes at least 2 steps
    # (REQ-G2D-186): finer than t asks, and still in air.
    sizes = np.diff(np.append(loops.row_starts, rows.shape[0]))
    loop_of_row = np.repeat(np.arange(sizes.size), sizes)
    totals = np.bincount(loop_of_row, weights=counts, minlength=sizes.size)
    short = (totals[loop_of_row] < _MIN_LOOP_VERTICES) & (flags == 1) & (rows[:, 6] != 0.0)
    counts[short & ~empty] = np.maximum(counts[short & ~empty], 2)
    return counts


def _flattened(
    loops: CurveRows, flags: NDArray[np.uint8], t_mm: float, portable: bool
) -> PolygonRegion:
    # Each joint once, as the first vertex of the row after it; each vertex the ID of its row.
    counts = _vertex_counts(loops, flags, t_mm)
    kept = counts > 0
    points = np.empty((int(counts.sum()), 2), dtype=np.float64)
    rows = loops.rows[kept]
    _kernels.geometry2d.flatten_rows(rows, flags[kept], counts[kept], portable, points)
    offsets = np.concatenate(([0], np.cumsum(counts)))
    arrays = (
        points,
        offsets[loops.row_starts],
        np.repeat(loops.ids, counts),
        np.zeros(points.shape[0], dtype=np.uint8),
    )
    for array in arrays:
        array.flags.writeable = False
    return PolygonRegion(*arrays)


def flatten_loops(tree: LoopTree, kind: RegionKind, ctx: Context) -> FlatRegion:
    """The tree's loops flattened within t_flat with every arc's error in air (DEC-G2D-028): each
    joint held once, as the first vertex of the row after it; each vertex carrying the ID of the
    row whose flattened edge starts there; no row that ends where it starts adds a vertex, and no
    loop keeps fewer than 3; no fixed nodes; lines and arcs only, so the extra clearance is 0. A
    step count beyond an int is a `ValueError`.

    Implements: REQ-G2D-115, REQ-G2D-116, REQ-G2D-119, REQ-G2D-127, REQ-G2D-185, REQ-G2D-186,
    REQ-G2D-199, REQ-G2D-200, REQ-G2D-230.
    """
    # Normalised loops have the inside on the left: air lies right of every arc of a material
    # region and left of every arc of an air region.
    sweep = tree.loops.rows[:, 6]
    inscribed = sweep < 0.0 if kind is RegionKind.MATERIAL else sweep > 0.0
    flags = inscribed.astype(np.uint8)
    region = _flattened(tree.loops, flags, ctx.tolerances.flatten_tol_mm, portable=False)
    return FlatRegion(region, 0.0)


def topology_flattening(loops: CurveRows, ctx: Context) -> PolygonRegion:
    """The loops with every arc replaced by its inscribed flattening within u, its vertices
    turned with the kernel's own sine and cosine, so they are the same on every platform; for the
    loop tree's decisions only (internal).

    Implements: REQ-G2D-029, REQ-G2D-152.
    """
    flags = np.ones(loops.rows.shape[0], dtype=np.uint8)
    return _flattened(loops, flags, ctx.tolerances.grid_unit_mm, portable=True)
