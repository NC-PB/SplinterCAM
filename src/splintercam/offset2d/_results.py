# SPDX-License-Identifier: Apache-2.0
"""What every offset2d kernel call shares on the Python side: the declared parameters, the output
arrays and their retry, the status as diagnostics, and the replay log (REQ-OFF-014, 018, 039,
041, 042)."""

import json
from collections.abc import Callable

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import (
    CANCELLED,
    TOLERANCE_DEFAULTS,
    Context,
    Diagnostic,
    Result,
    Severity,
)
from splintercam.geometry2d import PolygonRegion

from ._classes import SourceClasses

# Declared parameters, passed to the kernel as plain values (REQ-OFF-042, D-049).
BIAS_GRID_UNITS = TOLERANCE_DEFAULTS["offset_bias_grid_units"].default  # D-132
MARGIN_GRID_UNITS = TOLERANCE_DEFAULTS["rounding_margin_grid_units"].default  # D-132
JOIN_STEPS_MAX = TOLERANCE_DEFAULTS["join_steps_max"].default  # research 02, Parameters
MAX_SPAN_GRID_UNITS = TOLERANCE_DEFAULTS["grid_max_span_units"].default  # REQ-G2D-034
OK, _TOO_LARGE = 0, 1  # GridStatus in geometry2d's kernel/grid.hpp; 2 is a failure

# A kernel entry with its inputs bound: it writes into (points, starts, ids, fixed) as far as they
# reach and returns (status, points, loops), the counts it needed.
KernelCall = Callable[
    [NDArray[np.float64], NDArray[np.int64], NDArray[np.int64], NDArray[np.uint8]],
    tuple[int, int, int],
]


def vertex_classes(classes: SourceClasses, source_ids: NDArray[np.int64]) -> NDArray[np.int8]:
    """The class of each vertex's source ID (the IDs checked against `classes` before)."""
    return classes.classes[np.searchsorted(classes.ids, source_ids)].astype(np.int8)


def run_kernel(call: KernelCall, room: int) -> tuple[int, PolygonRegion | None]:
    """The kernel run with output arrays of `room` rows, and again with more when it needed them;
    the region read-only, or None with the status of a refusal or failure."""
    while True:
        points, starts = np.empty((room, 2)), np.empty(room, dtype=np.int64)
        ids, fixed = np.empty(room, dtype=np.int64), np.empty(room, dtype=np.uint8)
        status, n_points, n_loops = call(points, starts, ids, fixed)
        if max(n_points, n_loops) <= room:
            break
        room = max(n_points, n_loops)
    if status != OK:
        return status, None
    out = PolygonRegion(
        points[:n_points].copy(), starts[:n_loops].copy(), ids[:n_points].copy(),
        fixed[:n_points].copy(),
    )  # fmt: skip
    for array in (out.points, out.loop_starts, out.source_ids, out.fixed):
        array.flags.writeable = False
    return status, out


def outcome(
    status: int,
    region: PolygonRegion | None,
    dump: dict[str, object],
    diagnostics: list[Diagnostic],
    ctx: Context,
) -> Result[PolygonRegion]:
    """The kernel's status as a result: cancelled, refused, failed (the input logged for replay),
    empty or the region (REQ-OFF-014, 018, 039, 041)."""
    if ctx.cancel.is_cancelled:
        return Result(None, (*diagnostics, CANCELLED))
    if status == _TOO_LARGE:
        message = f"the input spans {MAX_SPAN_GRID_UNITS:.0f} grid units or more"
        return Result(None, (*diagnostics, Diagnostic("REGION_TOO_LARGE", Severity.ERROR, message)))
    if status != OK or region is None:
        ctx.logger.error("OFFSET_FAILED, kernel input for replay: %s", json.dumps(dump))
        failed = Diagnostic("OFFSET_FAILED", Severity.ERROR, "the call failed; input logged")
        return Result(None, (*diagnostics, failed))
    if region.loop_starts.size == 0:
        diagnostics.append(Diagnostic("OFFSET_EMPTY", Severity.INFO, "the region vanishes"))
    return Result(region, tuple(diagnostics))
