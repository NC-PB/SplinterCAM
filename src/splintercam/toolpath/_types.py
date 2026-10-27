# SPDX-License-Identifier: Apache-2.0
"""The link heights and the plan a strategy hands over: passes as curve rows at a level, all from
the approach point P back to it (research 10, Method; DEC-TP-001)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam.model import FlatEndMill, StockBox

CLEARANCE_ABOVE_STOCK_MM = 5.0  # D-062: clearance height over the stock top
RETRACT_ABOVE_STOCK_MM = 3.0  # D-062: retract height over the stock top


@dataclass(frozen=True, slots=True)
class LinkHeights:
    """h_c and h_r in the work frame (D-062)."""

    clearance_mm: float  # h_c = stock top + 5 (research 10, Method)
    retract_mm: float  # h_r = stock top + 3


def link_heights(stock: StockBox) -> LinkHeights:
    """h_c and h_r from the stock top alone; never raises (REQ-TP-001).

    Implements: REQ-TP-001.
    """
    top = stock.top_mm
    return LinkHeights(top + CLEARANCE_ABOVE_STOCK_MM, top + RETRACT_ABOVE_STOCK_MM)


@dataclass(frozen=True, slots=True, eq=False)
class LevelPass:
    """One pass in the plane at one level, from P back to P."""

    z_mm: float
    rows: NDArray[np.float64]  # (m, 7) curve rows [x0, y0, x1, y1, cx, cy, sweep]; sweep 0: a line
    role: NDArray[np.int8]  # (m,) cl Role: APPROACH, CUT or RETRACT
    feed_class: NDArray[np.int64]  # (m,) index into the header's feed classes


@dataclass(frozen=True, slots=True, eq=False)
class LinkPlan:
    """One operation's passes and how to reach them."""

    approach_xy_mm: tuple[float, float]  # P (research 22, Method 5)
    tool: FlatEndMill  # R = tool.radius_mm, for research 10 test 1's stock box grown by R
    plunge_feed_class: int  # the descent's feed class (research 10, Method 2)
    passes: tuple[LevelPass, ...]  # in cutting order
