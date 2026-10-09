# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for the geometry2d tests: contexts with other epsilons, diagnostic codes,
loops as curve rows, the kernel's tie candidates."""

import dataclasses
import math

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context, Result, ToleranceSet
from splintercam.geometry2d import CurveRows, LoopTree, curve_rows


def with_length_eps(ctx: Context, length_eps_mm: float) -> Context:
    """`ctx` with its length epsilon replaced, the rest of its tolerance set kept."""
    tolerances = ctx.tolerances
    changed = ToleranceSet(
        chord_tol_mm=tolerances.chord_tol_mm,
        length_eps_mm=length_eps_mm,
        angle_eps_rad=tolerances.angle_eps_rad,
        stage_shares=tolerances.stage_shares,
    )
    return dataclasses.replace(ctx, tolerances=changed)


def codes[T](result: Result[T]) -> list[str]:
    """The diagnostic codes of `result`, in order."""
    return [diagnostic.code for diagnostic in result.diagnostics]


def loop(rows: list[list[float]], ctx: Context) -> CurveRows:
    """One closed loop of curve rows [x0, y0, x1, y1, cx, cy, sweep], checked by `curve_rows`."""
    array = np.array(rows, dtype=np.float64)
    built = curve_rows(array, np.arange(len(rows), dtype=np.int64), np.zeros(1, np.int64), ctx)
    assert built.value is not None, built.diagnostics
    return built.value


def polygon(points: list[tuple[float, float]], ctx: Context) -> CurveRows:
    """The closed polygon through `points` as line rows."""
    nan = math.nan
    rows = [[*p, *q, nan, nan, 0.0] for p, q in zip(points, points[1:] + points[:1], strict=True)]
    return loop(rows, ctx)


def reversed_loop(rows: list[list[float]]) -> list[list[float]]:
    """The same loop the other way round: rows in reverse order, ends swapped, sweeps negated."""
    return [[x1, y1, x0, y0, cx, cy, -sweep] for x0, y0, x1, y1, cx, cy, sweep in rows[::-1]]


def nested_tree(loops: list[list[list[float]]], ctx: Context) -> LoopTree:
    """A tree of loops nested one inside the next, depth = position in `loops`, built directly
    (unchecked); the loops must already be normalised. Row IDs are 100, 101, ..."""
    rows = np.array([row for one in loops for row in one], dtype=np.float64)
    starts = np.cumsum([0] + [len(one) for one in loops[:-1]], dtype=np.int64)
    built = curve_rows(rows, 100 + np.arange(rows.shape[0], dtype=np.int64), starts, ctx)
    assert built.value is not None, built.diagnostics
    k = len(loops)
    return LoopTree(
        loops=built.value,
        parent=np.arange(k, dtype=np.int64) - 1,
        depth=np.arange(k, dtype=np.int64),
        input_index=np.arange(k, dtype=np.int64),
        crossing_points=np.empty((0, 2)),
        crossing_loops=np.empty((0, 2), dtype=np.int64),
    )


def polygons(loops: list[list[tuple[float, float]]], ctx: Context) -> CurveRows:
    """Closed polygons as line rows, one loop each, row IDs 100, 101, ..., checked by curve_rows."""
    nan = math.nan
    rows = [
        [*p, *q, nan, nan, 0.0]
        for points in loops
        for p, q in zip(points, points[1:] + points[:1], strict=True)
    ]
    starts = np.cumsum([0] + [len(p) for p in loops[:-1]], dtype=np.int64)
    ids = 100 + np.arange(len(rows), dtype=np.int64)
    built = curve_rows(np.array(rows, dtype=np.float64), ids, starts, ctx)
    assert built.value is not None, built.diagnostics
    return built.value


def nearest_ties(
    q: NDArray[np.float64],
    points: NDArray[np.float64],
    loop_starts: NDArray[np.int64],
    limit_mm: float,
    eps_mm: float,
) -> NDArray[np.int64]:
    """The kernel binding `nearest_ties` (REQ-G2D-242): (point, segment) rows, asked again with
    room for all when the first output was short."""
    kernel = _kernels.geometry2d
    out = np.empty((q.shape[0], 2), dtype=np.int64)
    count = kernel.nearest_ties(q, points, loop_starts, limit_mm, eps_mm, out)
    if count > out.shape[0]:
        out = np.empty((count, 2), dtype=np.int64)
        assert kernel.nearest_ties(q, points, loop_starts, limit_mm, eps_mm, out) == count
    return out[:count]
