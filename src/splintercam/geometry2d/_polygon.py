# SPDX-License-Identifier: Apache-2.0
"""Polygon regions: flattened loops with source IDs and fixed nodes at the kernel boundary
(research 01, Kernel arrays; D-059, D-084)."""

import enum
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam.foundation import Context, Diagnostic, Result, Severity

MIN_LOOP_VERTICES = 3  # a loop encloses nothing with fewer (research 01, Kernel arrays)


class RegionKind(enum.Enum):
    """What fills the region a set of loops bounds; it decides the air side of each arc."""

    MATERIAL = enum.auto()
    AIR = enum.auto()


@dataclass(frozen=True, slots=True)
class PolygonRegion:
    """Flat loops: `points` (n, 2) float64 in mm, `loop_starts` (k,) int64, `source_ids` (n,)
    int64, the ID of the edge that starts at each vertex, and `fixed` (n,) uint8, 1 for a fixed
    node. An outer boundary is CCW, a hole CW; no loop repeats its first vertex. Read-only. One
    built directly is unchecked; `polygon_region` is the validating entry.
    """

    points: NDArray[np.float64]
    loop_starts: NDArray[np.int64]
    source_ids: NDArray[np.int64]
    fixed: NDArray[np.uint8]


@dataclass(frozen=True, slots=True)
class FlatRegion:
    """A side-correct flattened region and the clearance every offset from it must add."""

    region: PolygonRegion
    extra_clearance_mm: float


def _structure_error(arrays: list[NDArray[np.generic]]) -> str | None:
    points, starts, ids, fixed = arrays
    n = points.shape[0] if points.ndim == 2 else -1
    expected = (
        (points, np.float64, (n, 2), "points"),
        (starts, np.int64, (starts.shape[0],) if starts.ndim == 1 else None, "loop_starts"),
        (ids, np.int64, (n,), "source_ids"),
        (fixed, np.uint8, (n,), "fixed"),
    )
    for array, dtype, shape, name in expected:
        if array.dtype != dtype or array.shape != shape:
            return (
                f"{name} must be {dtype.__name__} of shape {shape}, got {array.dtype} {array.shape}"
            )
    if np.any(fixed.astype(np.uint8) > 1):
        return "fixed must be 0 or 1"
    return None


def _loop_error(points: NDArray[np.float64], starts: NDArray[np.int64]) -> str | None:
    n = points.shape[0]
    if starts.size == 0:
        return None if n == 0 else "points without loops"
    if starts[0] != 0 or np.any((starts < 0) | (starts > n - MIN_LOOP_VERTICES)):
        return f"loop_starts must start at 0 and lie below {n} - 2: {starts}"
    ends = np.append(starts[1:], n)
    if np.any(ends - starts < MIN_LOOP_VERTICES):
        return f"loop_starts must start at 0 and ascend by at least 3 below {n}: {starts}"
    repeated = (points[ends - 1] == points[starts]).all(axis=1)
    if repeated.any():
        return f"loop {int(np.flatnonzero(repeated)[0])} repeats its first vertex at its end"
    if not np.isfinite(points).all():
        return "a point is not finite"
    return None


def polygon_region(
    points: ArrayLike, loop_starts: ArrayLike, source_ids: ArrayLike, fixed: ArrayLike, ctx: Context
) -> Result[PolygonRegion]:
    """Validated, read-only, C-contiguous copies of a polygon region, or `REGION_INVALID` when
    the arrays break the layout, before any kernel computation. An empty region is valid.

    Implements: REQ-G2D-183 to 187, REQ-G2D-201.
    """
    del ctx  # every public function takes the Context (SPEC, Public interface)
    copies = [np.array(a, order="C", copy=True) for a in (points, loop_starts, source_ids, fixed)]
    error = _structure_error(copies) or _loop_error(copies[0], copies[1])
    if error is not None:
        return Result(None, (Diagnostic("REGION_INVALID", Severity.ERROR, error),))
    for copy in copies:
        copy.flags.writeable = False
    return Result(PolygonRegion(*copies))
