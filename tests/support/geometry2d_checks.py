# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for the geometry2d tests: contexts with other epsilons, diagnostic codes,
loops as curve rows."""

import dataclasses
import math

import numpy as np

from splintercam.foundation import Context, Result, ToleranceSet
from splintercam.geometry2d import CurveRows, curve_rows


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
