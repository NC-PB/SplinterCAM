# SPDX-License-Identifier: Apache-2.0
"""The plan's checks, REQ-TP-001 and 007 to 012, rule by rule in the order of REQ-TP-013: a pass
rule runs over every pass before the next rule, so a rule sees only passes that passed the rules
before it. Exact comparisons (bit for bit as values) but REQ-TP-012's (DEC-TP-004)."""

import math
from collections.abc import Callable
from typing import cast

import numpy as np
from numpy.typing import NDArray

from splintercam.cl import ClHeader, Role
from splintercam.model import StockBox

from ._types import LevelPass, LinkHeights, LinkPlan

# (column, dtype, shape after the row axis, shape as text)
_COLUMNS = (
    ("rows", np.float64, (7,), "(m, 7)"),
    ("role", np.int8, (), "(m,)"),
    ("feed_class", np.int64, (), "(m,)"),
)
_PASS_ROLES = np.array([Role.APPROACH, Role.CUT, Role.RETRACT], dtype=np.int8)


def _heights(top: float, h: LinkHeights) -> str | None:
    if math.isfinite(top) and h.retract_mm < h.clearance_mm:
        return None
    return f"stock top {top!r} gives no h_r below h_c ({h.retract_mm!r}, {h.clearance_mm!r})"


def _header(header: ClHeader, h: LinkHeights) -> str | None:
    if header.clearance_height_mm != h.clearance_mm:
        return f"header clearance height {header.clearance_height_mm!r} is not h_c"
    if header.retract_height_mm != h.retract_mm:
        return f"header retract height {header.retract_height_mm!r} is not h_r"
    return None


def _fields(plan: LinkPlan) -> str | None:
    if not plan.passes:
        return "no pass"
    if not all(math.isfinite(value) for value in plan.approach_xy_mm):
        return f"approach point {plan.approach_xy_mm!r} is not finite"
    if plan.plunge_feed_class < 0:
        return f"plunge feed class {plan.plunge_feed_class} is negative"
    return None


def _columns(level: LevelPass) -> str | None:
    # A subclass is refused, as cl's REQ-CL-004: a masked array hides its masked values.
    for name, dtype, tail, shape in _COLUMNS:
        value: object = getattr(level, name)
        array = cast("NDArray[np.generic]", value)
        if type(value) is not np.ndarray or array.dtype != dtype or array.shape[1:] != tail:
            return f"column {name} must be a {np.dtype(dtype).name} array of shape {shape}"
        if array.ndim != 1 + len(tail) or array.shape[0] != level.rows.shape[0]:
            return f"column {name} must have one entry per row of rows"
    if level.rows.shape[0] == 0:
        return "no row"
    wrong = np.flatnonzero(~np.isin(level.role, _PASS_ROLES))
    if wrong.size:
        return f"row {wrong[0]}: role {level.role[wrong[0]]} is not APPROACH, CUT or RETRACT"
    return None


def _level(level: LevelPass, retract: float) -> str | None:
    # Research 10, Method 2: the descent goes down from h_r.
    if math.isfinite(level.z_mm) and level.z_mm < retract:
        return None
    return f"level {level.z_mm!r} is not finite and below h_r {retract!r}"


def _chain(level: LevelPass, at: tuple[float, float]) -> str | None:
    # Research 10, Method 3; the record stores ends only, so a gap would be lost (research 26).
    rows = level.rows
    if not (rows[0, 0] == at[0] and rows[0, 1] == at[1]):
        return "row 0: the pass does not start at P"
    gaps = np.flatnonzero((rows[1:, 0:2] != rows[:-1, 2:4]).any(axis=1))
    if gaps.size:
        return f"row {gaps[0] + 1}: does not start where row {gaps[0]} ends"
    if not (rows[-1, 2] == at[0] and rows[-1, 3] == at[1]):
        return f"row {rows.shape[0] - 1}: the pass does not end at P"
    return None


def _descent(plan: LinkPlan, stock: StockBox) -> str | None:
    # DEC-TP-004: the stock box grown by R with round corners, touching inside; one float64
    # expression in scalar Python floats, in this order (D-055, REQ-TP-014).
    px, py = (float(value) for value in plan.approach_xy_mm)
    (x_min, y_min, _), (x_max, y_max, _) = stock.min_mm, stock.max_mm
    dx = max(x_min - px, 0.0, px - x_max)
    dy = max(y_min - py, 0.0, py - y_max)
    radius = plan.tool.radius_mm
    if dx * dx + dy * dy <= radius * radius:
        return f"approach point {(px, py)!r} lies within R = {radius!r} of the stock box"
    return None


def _each(plan: LinkPlan, rule: Callable[[LevelPass], str | None]) -> str | None:
    # The first pass breaking `rule`, named by its index.
    for index, level in enumerate(plan.passes):
        if (text := rule(level)) is not None:
            return f"pass {index}{', ' if text.startswith('row ') else ': '}{text}"
    return None


def plan_breach(
    header: ClHeader, plan: LinkPlan, stock: StockBox, h: LinkHeights
) -> tuple[str, str] | None:
    """The first rule broken and its text, naming the first pass and row breaking it, or None
    (REQ-TP-013). Each rule runs only once the rules before it hold."""
    rules: tuple[tuple[str, Callable[[], str | None]], ...] = (
        ("REQ-TP-001", lambda: _heights(stock.top_mm, h)),
        ("REQ-TP-007", lambda: _header(header, h)),
        ("REQ-TP-008", lambda: _fields(plan)),
        ("REQ-TP-009", lambda: _each(plan, _columns)),
        ("REQ-TP-010", lambda: _each(plan, lambda level: _level(level, h.retract_mm))),
        ("REQ-TP-011", lambda: _each(plan, lambda level: _chain(level, plan.approach_xy_mm))),
        ("REQ-TP-012", lambda: _descent(plan, stock)),
    )
    for requirement, rule in rules:
        if (text := rule()) is not None:
            return requirement, text
    return None
