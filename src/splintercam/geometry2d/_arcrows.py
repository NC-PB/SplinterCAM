# SPDX-License-Identifier: Apache-2.0
"""Array forms of the arc constructions and the bounding box, for importers that build many rows
at once (DEC-G2D-044). Each row equals the per-curve function's result bit for bit: the kernel
ports `arc_from_bulge`, `make_arc` and `bounding_box` operation for operation."""

from dataclasses import dataclass
from enum import IntEnum
from typing import cast

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import Context

from ._rows import _ROW_WIDTH  # pyright: ignore[reportPrivateUsage] (one module)


class RowStatus(IntEnum):
    """What became of one row; the codes match the per-curve functions' diagnostics."""

    OK = 0
    CURVE_INVALID = 1
    ARC_INCONSISTENT = 2


@dataclass(frozen=True, slots=True)
class BuiltRows:
    """Curve rows (n, 7) and their `RowStatus` (n,); a failed row is all NaN."""

    rows: NDArray[np.float64]
    status: NDArray[np.int8]


def _array(name: str, value: object, shape: tuple[int, ...]) -> NDArray[np.float64]:
    # `value` as a C-contiguous float64 array of `shape`, -1 matching any length (REQ-G2D-247).
    if not isinstance(value, np.ndarray):
        message = f"{name} must be a float64 array of shape {shape}, got {type(value).__name__}"
        raise ValueError(message)
    array = cast("NDArray[np.generic]", value)
    if (
        array.dtype != np.float64
        or array.ndim != len(shape)
        or any(want not in (-1, got) for want, got in zip(shape, array.shape, strict=True))
    ):
        message = (
            f"{name} must be a float64 array of shape {shape}, got {array.dtype} {array.shape}"
        )
        raise ValueError(message)
    return np.ascontiguousarray(array, dtype=np.float64)


def _build(
    p0: NDArray[np.float64], p1: NDArray[np.float64], values: NDArray[np.float64], name: str,
    ctx: Context,
) -> BuiltRows:  # fmt: skip
    # `name` says what the values are: "bulges" or "sweeps_rad".
    start = _array("p0", p0, (-1, 2))
    n = start.shape[0]
    end, given = _array("p1", p1, (n, 2)), _array(name, values, (n,))
    rows = np.empty((n, _ROW_WIDTH), dtype=np.float64)
    status = np.empty(n, dtype=np.int8)
    eps = ctx.tolerances.length_eps_mm
    sweeps = name == "sweeps_rad"
    _kernels.geometry2d.rows_from_ends(start, end, given, sweeps, eps, rows, status)
    return BuiltRows(rows, status)


def rows_from_bulges(
    p0: NDArray[np.float64], p1: NDArray[np.float64], bulges: NDArray[np.float64], ctx: Context
) -> BuiltRows:
    """Per row the curve `arc_from_bulge(p0[i], p1[i], bulges[i])` as a curve row: a line with a
    NaN centre and sweep 0, or the arc; `CURVE_INVALID` or `ARC_INCONSISTENT` where it fails.
    kernel: arcs.cpp.

    Implements: REQ-G2D-243, REQ-G2D-246, REQ-G2D-247.
    """
    return _build(p0, p1, bulges, "bulges", ctx)


def rows_from_sweeps(
    p0: NDArray[np.float64], p1: NDArray[np.float64], sweeps_rad: NDArray[np.float64], ctx: Context
) -> BuiltRows:
    """Per row the arc from p0 to p1 with the given sweep, its centre on the bisector as for the
    bulge tan(φ/4), its sweep kept as given; a line where that bulge gives one. `CURVE_INVALID`
    for a sweep that is not finite, 0 or of size 2π or more. kernel: arcs.cpp.

    Implements: REQ-G2D-244, REQ-G2D-246, REQ-G2D-247.
    """
    return _build(p0, p1, sweeps_rad, "sweeps_rad", ctx)


def row_boxes(rows: NDArray[np.float64], ctx: Context) -> NDArray[np.float64]:
    """Per curve row its `bounding_box` as [x_min, y_min, x_max, y_max] (m, 4). kernel: arcs.cpp.

    Implements: REQ-G2D-245, REQ-G2D-246, REQ-G2D-247.
    """
    del ctx  # every public function takes the Context (SPEC, Public interface)
    checked = _array("rows", rows, (-1, _ROW_WIDTH))
    boxes = np.empty((checked.shape[0], 4), dtype=np.float64)
    _kernels.geometry2d.row_boxes(checked, boxes)
    return boxes


def check_arc_rows(rows: NDArray[np.float64], ctx: Context) -> NDArray[np.int8]:
    """Per curve row its `RowStatus`, the row as given: `OK` for a line with finite ends (its
    centre not read) or a consistent arc; `CURVE_INVALID` for an end, an arc's centre or sweep
    that is not finite, |sweep| > 2π or a radius at or below eps_len; `ARC_INCONSISTENT` for an
    arc that breaks REQ-G2D-042 or 043. kernel: arcs.cpp.

    Implements: REQ-G2D-248, REQ-G2D-246, REQ-G2D-247.
    """
    checked = _array("rows", rows, (-1, _ROW_WIDTH))
    status = np.empty(checked.shape[0], dtype=np.int8)
    _kernels.geometry2d.check_arc_rows(checked, ctx.tolerances.length_eps_mm, status)
    return status
