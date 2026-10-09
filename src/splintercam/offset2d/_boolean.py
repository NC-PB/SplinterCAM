# SPDX-License-Identifier: Apache-2.0
"""Booleans of regions (research 02, Booleans): union, difference and intersection in one Clipper2
call on geometry2d's grid, source IDs over the edges of both operands."""

import enum

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import CANCELLED, Context, Result
from splintercam.geometry2d import PolygonRegion

from ._classes import SourceClasses, check_classes
from ._results import MARGIN_GRID_UNITS, MAX_SPAN_GRID_UNITS, outcome, run_kernel, vertex_classes


class BooleanOp(enum.Enum):
    """The Boolean of two regions, numbered as the kernel's ClipOp."""

    UNION = 0
    DIFFERENCE = 1  # a - b
    INTERSECTION = 2


def boolean(
    a: PolygonRegion, b: PolygonRegion, op: BooleanOp, classes: SourceClasses, ctx: Context
) -> Result[PolygonRegion]:
    """The union, difference a - b or intersection of two regions, with the Positive fill rule
    for both. Each output edge takes the source ID of the nearest edge of either operand, material
    first where edges of two classes overlap (D-059). An empty result carries `OFFSET_EMPTY`.

    Implements: REQ-OFF-030, REQ-OFF-031, REQ-OFF-035, REQ-OFF-036, REQ-OFF-039.
    """
    if op not in tuple(BooleanOp):  # a caller without type checks
        raise ValueError(f"the operation must be a BooleanOp, got {op!r}")
    check_classes(classes, np.concatenate([a.source_ids, b.source_ids]))
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    status, region = clip(a, b, op, classes, ctx)

    def dump() -> dict[str, object]:
        """The kernel's input, for `tools/replay` once it exists (REQ-OFF-014)."""
        return {
            "op": op.name,
            "a": {"points": a.points.tolist(), "loop_starts": a.loop_starts.tolist(),
                  "source_ids": a.source_ids.tolist()},
            "b": {"points": b.points.tolist(), "loop_starts": b.loop_starts.tolist(),
                  "source_ids": b.source_ids.tolist()},
            "classes": {"ids": classes.ids.tolist(), "classes": classes.classes.tolist()},
            "grid_unit_mm": ctx.tolerances.grid_unit_mm,
            "max_span_grid_units": MAX_SPAN_GRID_UNITS,
            "margin_grid_units": MARGIN_GRID_UNITS,
        }  # fmt: skip

    return outcome(status, region, dump, [], ctx)


def clip(
    a: PolygonRegion, b: PolygonRegion, op: BooleanOp, classes: SourceClasses, ctx: Context
) -> tuple[int, PolygonRegion | None]:
    """The kernel call of `boolean`, also for `stock_layer`: the IDs from the edges of both."""
    points = np.ascontiguousarray(np.concatenate([a.points, b.points]), dtype=np.float64)
    starts = np.concatenate([a.loop_starts, b.loop_starts + a.points.shape[0]]).astype(np.int64)
    ids = np.ascontiguousarray(np.concatenate([a.source_ids, b.source_ids]), dtype=np.int64)
    per_vertex = vertex_classes(classes, ids)
    tol = ctx.tolerances
    # Both ends of an output edge lie on one input edge rounded to the grid, a crossing within
    # about 1.41 grid units of it, so its middle lies within the rounding margin of that edge: the
    # reach. Two operands round the same wall to points up to 2.83 grid units apart (REQ-G2D-030),
    # so edges within half the margin of the nearest tie, and material wins (D-059; DEC-OFF-014).
    margin_mm = MARGIN_GRID_UNITS * tol.grid_unit_mm
    grid = (tol.grid_unit_mm, MAX_SPAN_GRID_UNITS, margin_mm / 2.0, margin_mm)
    a_points = np.ascontiguousarray(a.points, dtype=np.float64)
    b_points = np.ascontiguousarray(b.points, dtype=np.float64)
    a_starts = np.ascontiguousarray(a.loop_starts, dtype=np.int64)
    b_starts = np.ascontiguousarray(b.loop_starts, dtype=np.int64)

    def call(
        out_points: NDArray[np.float64],
        out_starts: NDArray[np.int64],
        out_ids: NDArray[np.int64],
        out_fixed: NDArray[np.uint8],
    ) -> tuple[int, int, int]:
        return _kernels.offset2d.clip_regions(
            a_points, a_starts, b_points, b_starts, points, starts, ids, per_vertex,
            op.value, grid, out_points, out_starts, out_ids, out_fixed,
        )  # fmt: skip

    return run_kernel(call, 2 * points.shape[0] + 64)
