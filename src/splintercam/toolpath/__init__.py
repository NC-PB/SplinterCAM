# SPDX-License-Identifier: Apache-2.0
"""toolpath: the links between and around an operation's passes (see SPEC.md)."""

from ._link import link_operation
from ._types import (
    CLEARANCE_ABOVE_STOCK_MM,
    RETRACT_ABOVE_STOCK_MM,
    LevelPass,
    LinkHeights,
    LinkPlan,
    link_heights,
)

__all__ = [
    "CLEARANCE_ABOVE_STOCK_MM",
    "RETRACT_ABOVE_STOCK_MM",
    "LevelPass",
    "LinkHeights",
    "LinkPlan",
    "link_heights",
    "link_operation",
]
