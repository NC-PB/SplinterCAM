# SPDX-License-Identifier: Apache-2.0
"""`plan_profile`: the values checked, the centre path from offset2d's grow, S and P, the passes
and the record from toolpath's links (research 22, Method 1 to 6)."""

import numpy as np

from splintercam.cl import ClHeader, ClOperation
from splintercam.foundation import CANCELLED, Context, Diagnostic, Result
from splintercam.geometry2d import PolygonRegion, RegionKind, orient2d
from splintercam.offset2d import EdgeClass, SourceClasses, offset_region
from splintercam.toolpath import LinkPlan, link_heights, link_operation

from ._approach import start_and_approach
from ._checks import checked_input, error, value_errors
from ._passes import PLUNGE_CLASS, level_passes, levels
from ._types import ProfileInput, Values


def _centre_path(task: ProfileInput, t_mm: float, ctx: Context) -> Result[PolygonRegion]:
    # REQ-PRF-010: every source ID of class MATERIAL; offset2d's diagnostics passed on in order.
    ids = np.unique(task.contour.ids)
    classes = SourceClasses(ids, np.full(ids.size, EdgeClass.MATERIAL, dtype=np.int8))
    return offset_region(task.contour, RegionKind.MATERIAL, t_mm, classes, ctx)


def _header(task: ProfileInput, v: Values, axial_offset_mm: float) -> ClHeader:
    # REQ-PRF-018: the feed classes in the order of _passes' CUT_CLASS and PLUNGE_CLASS.
    op, heights = task.operation, link_heights(task.stock)
    feeds = (("cut", v.cut_feed_mm_per_min), ("plunge", v.plunge_feed_mm_per_min))
    return ClHeader(op.name, (), op.tool_number, op.point_number, axial_offset_mm, op.spindle_rpm,
                    op.tol_mm, feeds, heights.clearance_mm, heights.retract_mm)  # fmt: skip


def _link_plan(
    task: ProfileInput, v: Values, region: PolygonRegion, ctx: Context
) -> LinkPlan | Diagnostic:
    # The first of REQ-PRF-010 (one loop) and 015 (a free approach) that fails, or the passes
    # from P round the clockwise loop (REQ-PRF-012 to 017).
    if (count := region.loop_starts.size) != 1:
        return error(task, "PROFILE_REGION", f"the centre path has {count} loops, not one")
    p = region.points  # DEC-PRF-007 (6): the turn at the smallest vertex, convex (REQ-OFF-038)
    if orient2d(p[-1:], p[:1], p[1:2])[0] <= 0:
        raise ValueError(f"operation {task.operation.name!r}: offset2d's outer loop is not CCW")
    arc_ids = task.contour.ids[task.contour.rows[:, 6] != 0.0]
    r = task.tool.radius_mm
    loop, approach = start_and_approach(region, arc_ids, task.stock, r + v.air_gap_ratio * r)
    if loop is None:
        text = f"the approach from the smallest vertex {approach!r} crosses the part"
        return error(task, "PROFILE_APPROACH_BLOCKED", text)
    zs = levels(v.z_top_mm, v.z_bottom_mm, v.stepdown_mm, ctx.tolerances.length_eps_mm)
    return LinkPlan(approach, task.tool, PLUNGE_CLASS, level_passes(loop, approach, zs))


def plan_profile(task: ProfileInput, ctx: Context) -> Result[ClOperation]:
    """The outside profile of `task.contour` as one operation of the toolpath record, or no value
    and the diagnostics that stopped it; `ValueError` for a broken precondition.

    Implements: REQ-PRF-002 to REQ-PRF-022.
    """
    values, point = checked_input(task, ctx)
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    if errors := value_errors(task, values, ctx):
        return Result(None, tuple(errors))
    offset = _centre_path(task, task.tool.radius_mm + values.allowance_mm, ctx)
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    if offset.value is None:
        return Result(None, offset.diagnostics)
    plan = _link_plan(task, values, offset.value, ctx)
    if isinstance(plan, Diagnostic):
        return Result(None, (*offset.diagnostics, plan))
    header = _header(task, values, point.axial_offset_mm)
    return Result(link_operation(header, plan, task.stock, ctx), offset.diagnostics)
