# SPDX-License-Identifier: Apache-2.0
"""One operation's line on the sheet: its header values (REQ-SHT-009), approach points and
witness marks, its reach below h_c (REQ-SHT-012, DEC-SHT-002) and where it ends (REQ-SHT-016)."""

import math

import numpy as np

from splintercam.cl import ClOperation, MoveKind
from splintercam.foundation import Context
from splintercam.geometry2d import row_boxes
from splintercam.model import StockBox

from ._approach import approach_points, move_starts, witness_marks
from ._checks import Planned
from ._types import Box3, SheetOperation


def reach_below(written: ClOperation, radius: float, ctx: Context) -> Box3 | None:
    """The XY box of the tool centre over every move whose end or known start lies below h_c
    (an ARC by geometry2d's arc box, REQ-G2D-214), grown by R, from the lowest end to h_c."""
    moves, clearance = written.moves, written.header.clearance_height_mm
    end, starts = moves.end_mm, move_starts(moves)
    low = (end[:, 2] < clearance) | (starts[:, 2] < clearance)  # NaN starts: False
    if not low.any():
        return None
    arcs = low & (moves.kind == MoveKind.ARC)
    rows = np.column_stack(
        (starts[arcs, :2], end[arcs, :2], moves.centre_mm[arcs], moves.sweep_rad[arcs])
    )
    boxes = row_boxes(rows, ctx)
    xs = np.concatenate((end[low, 0], starts[low, 0], boxes[:, 0], boxes[:, 2]))
    ys = np.concatenate((end[low, 1], starts[low, 1], boxes[:, 1], boxes[:, 3]))
    return Box3(
        (float(xs.min()) - radius, float(ys.min()) - radius, float(end[:, 2].min())),
        (float(xs.max()) + radius, float(ys.max()) + radius, clearance),
    )


def sheet_operation(
    written: ClOperation, planned: Planned, stock: StockBox, ctx: Context
) -> SheetOperation:
    """The operation's values; `planned` is the job's operation, tool and point that REQ-SHT-001
    matched to the record's operation."""
    operation, tool, point = planned
    header, moves = written.header, written.moves
    radius = tool.radius_mm
    last = moves.end_mm[-1]
    return SheetOperation(
        name=header.name,
        strategy=operation.strategy,
        tool_number=header.tool_number,
        point_number=header.point_number,
        axial_offset_mm=header.axial_offset_mm,
        register_radius_mm=point.register_radius_mm,  # DEC-SHT-011: not in the header yet
        spindle_rpm=header.spindle_rpm,
        tol_mm=header.tol_mm,
        feeds=header.feed_classes,
        clearance_mm=header.clearance_height_mm,
        retract_mm=header.retract_height_mm,
        lowest_mm=float(moves.end_mm[:, 2].min()),
        approach_points=approach_points(written, stock, radius),
        witness_marks=witness_marks(moves, radius),
        reach=reach_below(written, radius, ctx),
        # DEC-SHT-010: move 0 alone ends at the tool-change position, XY unknown (NaN).
        end_xy_mm=None if math.isnan(last[0]) else (float(last[0]), float(last[1])),
    )
