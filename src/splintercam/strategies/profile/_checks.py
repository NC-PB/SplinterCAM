# SPDX-License-Identifier: Apache-2.0
"""The preconditions, which raise, and the value checks, which are diagnostics, all reported in
the order of REQ-PRF-003 to 009 (REQ-PRF-020; DEC-PRF-005)."""

import math

from splintercam.foundation import Context, Diagnostic, Severity, ToleranceSet
from splintercam.geometry2d import row_boxes
from splintercam.model import MeasurementPoint
from splintercam.toolpath import link_heights

from ._passes import first_level
from ._types import DECLARATIONS, MIN_STEPDOWN_MM, STRATEGY_ID, ProfileInput, Values


def error(task: ProfileInput, code: str, text: str) -> Diagnostic:
    # An error at the operation, without model's index (DEC-PRF-005).
    return Diagnostic(code, Severity.ERROR, text, f"operation ({task.operation.name})")


def checked_input(task: ProfileInput, ctx: Context) -> tuple[Values, MeasurementPoint]:
    # REQ-PRF-002: the values and the tool's point, or `ValueError` naming the broken precondition.
    op, tool = task.operation, task.tool
    names = tuple(name for name, _ in op.parameters)
    point = next((p for p in tool.points if p.number == op.point_number), None)
    problems = (
        (op.strategy != STRATEGY_ID, f"strategy {op.strategy!r} is not {STRATEGY_ID!r}"),
        (names != tuple(d.name for d in DECLARATIONS), f"parameters {names} are not the declared"),
        (tool.number != op.tool_number, f"tool {tool.number} is not the operation's"),
        (point is None, f"the tool has no point {op.point_number}"),
        (task.contour.row_starts.size != 1, "the contour is not one loop"),
        (ToleranceSet.for_operation(op.tol_mm).value != ctx.tolerances,
         "ctx.tolerances is not the operation's tolerance set"),
    )  # fmt: skip
    for broken, problem in problems:
        if broken:
            raise ValueError(f"operation {op.name!r}: {problem}")
    assert point is not None
    return Values(*(value for _, value in op.parameters)), point


def _levels(task: ProfileInput, v: Values, ctx: Context) -> list[tuple[str, str]]:
    # REQ-PRF-005: every descent goes down from h_r (toolpath REQ-TP-001, 010); a first pass deeper
    # than the step-down below the stock top (AQ-016, item 3 (a); DEC-PRF-004).
    eps, top = ctx.tolerances.length_eps_mm, task.stock.top_mm
    out: list[tuple[str, str]] = []
    heights = link_heights(task.stock)
    z_1 = first_level(v.z_top_mm, v.z_bottom_mm, v.stepdown_mm, eps)
    if not (heights.retract_mm < heights.clearance_mm and z_1 < heights.retract_mm):
        out.append(("PROFILE_TOP_TOO_HIGH",
                    f"the first level {z_1!r} is not below h_r {heights.retract_mm!r} "
                    f"(h_c {heights.clearance_mm!r})"))  # fmt: skip
    if v.z_top_mm < top and top - z_1 > v.stepdown_mm + eps:
        out.append(("PROFILE_FIRST_PASS_DEEP",
                    f"the first pass cuts {top - z_1!r} mm below the stock top {top!r}, more "
                    f"than the step-down {v.stepdown_mm!r}"))  # fmt: skip
    return out


def _stock_sides(task: ProfileInput, ctx: Context) -> list[str]:
    # REQ-PRF-009: the part's box in XY inside the stock's, ends included (research 22, Method 5).
    boxes = row_boxes(task.contour.rows, ctx)
    (x0, y0, _), (x1, y1, _) = task.stock.min_mm, task.stock.max_mm
    sides = (
        ("x min", float(boxes[:, 0].min()) < x0),
        ("y min", float(boxes[:, 1].min()) < y0),
        ("x max", float(boxes[:, 2].max()) > x1),
        ("y max", float(boxes[:, 3].max()) > y1),
    )
    return [side for side, out in sides if out]


def _step_down(step: float, flute: float, countable: bool) -> str | None:
    # REQ-PRF-008: at most the flute length, at least 0.01 mm, and a finite pass count (AQ-030).
    if step > flute:
        return f"step-down {step!r} exceeds the flute length {flute!r}"
    if not step >= MIN_STEPDOWN_MM:
        return f"step-down {step!r} is below {MIN_STEPDOWN_MM!r}"
    return None if countable else f"step-down {step!r} gives no finite pass count for the depth"


def value_errors(task: ProfileInput, v: Values, ctx: Context) -> list[Diagnostic]:
    # REQ-PRF-020: every failing value check, REQ-PRF-003 to 009 in that order.
    r, flute = task.tool.radius_mm, task.tool.flute_length_mm
    top, bottom = task.stock.top_mm, task.stock.min_mm[2]
    gap, eps = v.air_gap_ratio * r, ctx.tolerances.length_eps_mm
    found: list[tuple[str, str]] = []
    if not v.allowance_mm > -r:  # D-150: t = R + s > 0
        found.append(("PROFILE_ALLOWANCE", f"allowance {v.allowance_mm!r} is not above -R {-r!r}"))
    # AQ-030: a pass count from a quotient that is not finite would overflow; no levels then.
    countable = v.stepdown_mm > 0.0 and math.isfinite((v.z_top_mm - v.z_bottom_mm) / v.stepdown_mm)
    if not v.z_bottom_mm < v.z_top_mm:  # research 22, trap 3
        found.append(("PROFILE_DEPTH_INVALID",
                      f"z_bottom {v.z_bottom_mm!r} is not below z_top {v.z_top_mm!r}"))  # fmt: skip
    elif countable:
        found += _levels(task, v, ctx)
    if v.z_bottom_mm < bottom:  # AQ-016, item 5 (a)
        text = f"z_bottom {v.z_bottom_mm!r} is below the stock bottom {bottom!r}"
        found.append(("PROFILE_BELOW_STOCK", text))
    if top - v.z_bottom_mm > flute:  # from the stock top, DEC-PRF-004
        text = f"depth {top - v.z_bottom_mm!r} below the stock top exceeds the flute {flute!r}"
        found.append(("PROFILE_TOO_DEEP", text))
    if (step := _step_down(v.stepdown_mm, flute, countable)) is not None:
        found.append(("PROFILE_STEP_DOWN", step))
    if sides := _stock_sides(task, ctx):
        found.append(("PROFILE_STOCK_SMALL", f"the part lies past the stock's {', '.join(sides)}"))
    if not gap > eps:  # DEC-PRF-003
        found.append(("PROFILE_AIR_GAP", f"air gap {gap!r} mm is not above eps_len {eps!r}"))
    return [error(task, code, text) for code, text in found]
