# SPDX-License-Identifier: Apache-2.0
"""`link_operation`: the plan checked, its links built around the passes and the record handed to
cl's `make_operation` (research 10, Method 1 to 5). A Python loop over passes only; a pass's rows
are copied into the columns vectorised (split rule; DEC-TP-003)."""

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from splintercam.cl import (
    NO_FEED_CLASS,
    ClHeader,
    ClMoves,
    ClOperation,
    MoveKind,
    Role,
    make_operation,
)
from splintercam.foundation import Context
from splintercam.model import StockBox

from ._checks import plan_breach
from ._types import LevelPass, LinkPlan, link_heights

type _Block = tuple[NDArray[Any], ...]  # the seven columns of ClMoves, in its order
_DTYPES = (np.int8, np.int8, np.float64, np.float64, np.float64, np.int64, np.float64)


def _single(kind: MoveKind, role: Role, end: tuple[float, ...], feed: int, link: float) -> _Block:
    # One RAPID or descent: centre NaN and sweep +0.0, the fill values of cl's REQ-CL-013.
    values = ([kind], [role], [end], [(math.nan, math.nan)], [0.0], [feed], [link])
    return tuple(np.array(value, dtype=dtype) for value, dtype in zip(values, _DTYPES, strict=True))


def _rapid(x: float, y: float, z: float) -> _Block:
    # Research 10, Method 5: a rapid's link height is the height it moves at, h_c or h_r.
    return _single(MoveKind.RAPID, Role.LINK, (x, y, z), NO_FEED_CLASS, z)


def _cut(level: LevelPass) -> _Block:
    # REQ-TP-006: an ARC where the sweep is not 0 (-0.0 is 0); a LINE gets the fill values.
    rows, arc = level.rows, level.rows[:, 6] != 0.0
    z = np.full(rows.shape[0], level.z_mm, dtype=np.float64)  # float64 even for an int z_mm
    kind = np.where(arc, MoveKind.ARC, MoveKind.LINE).astype(np.int8)
    centre = np.where(arc[:, np.newaxis], rows[:, 4:6], np.nan)
    sweep = np.where(arc, rows[:, 6], 0.0)
    end = np.column_stack((rows[:, 2:4], z))
    return kind, level.role, end, centre, sweep, level.feed_class, np.full_like(z, np.nan)


def _moves(plan: LinkPlan, clearance: float, retract: float) -> ClMoves:
    # Research 10, Method 1 to 4 (REQ-TP-002): Z first, over P at h_c; per pass down to h_r, feed
    # down to z_i, the pass, up to h_c.
    px, py = plan.approach_xy_mm
    blocks = [_rapid(math.nan, math.nan, clearance), _rapid(px, py, clearance)]
    for level in plan.passes:
        descent = (px, py, level.z_mm)
        plunge = _single(MoveKind.LINE, Role.APPROACH, descent, plan.plunge_feed_class, math.nan)
        blocks += [_rapid(px, py, retract), plunge, _cut(level), _rapid(px, py, clearance)]
    return ClMoves(*(np.concatenate(column) for column in zip(*blocks, strict=True)))


def link_operation(header: ClHeader, plan: LinkPlan, stock: StockBox, ctx: Context) -> ClOperation:
    """The operation of `plan`'s passes with their links, as `make_operation` returns it, or
    `ValueError` naming the first rule broken and its first pass and row (REQ-TP-013); cl's
    `ValueError` passes through unchanged.

    Implements: REQ-TP-001 to REQ-TP-014.
    """
    heights = link_heights(stock)
    if (breach := plan_breach(header, plan, stock, heights)) is not None:
        raise ValueError(f"operation {header.name!r}: {breach}")
    return make_operation(header, _moves(plan, heights.clearance_mm, heights.retract_mm), ctx)
