# SPDX-License-Identifier: Apache-2.0
"""The profile's declared parameters, its typed input and the values read from an operation
(research 22, Parameters; D-049; AQ-014)."""

import math
from dataclasses import dataclass

from splintercam.geometry2d import CurveRows
from splintercam.model import FlatEndMill, Operation, ParameterDeclaration, StockBox, Unit

STRATEGY_ID = "profile"


MIN_STEPDOWN_MM = 0.01  # Peter, AQ-030 (a): below it a step-down is a typing error
MAX_AIR_GAP_RATIO = 2.0  # Peter, AQ-031 (a): g at most 2R


def _declare(name: str, unit: Unit, default: float | None, low: float, source: str
             ) -> ParameterDeclaration:  # fmt: skip
    # Open at both ends: (low, inf), as REQ-PRF-001 writes the ranges; "(-inf, inf)" in messages.
    return ParameterDeclaration(name, unit, default, low, math.inf, True, True, source)


# [0.01, inf) and (0, 2]: closed at Peter's ends (AQ-030, AQ-031).
_STEPDOWN = ParameterDeclaration("stepdown_mm", Unit.MM, None, MIN_STEPDOWN_MM, math.inf, False,
                                 True, "research 22, Parameters; AQ-030")  # fmt: skip
_AIR_GAP = ParameterDeclaration("air_gap_ratio", Unit.RATIO, 0.2, 0.0, MAX_AIR_GAP_RATIO, True,
                                False, "D-079; research 22, Parameters; AQ-031")  # fmt: skip
DECLARATIONS: tuple[ParameterDeclaration, ...] = (
    _declare("allowance_mm", Unit.MM, 0.0, -math.inf, "D-150; research 22, Parameters"),
    _declare("z_top_mm", Unit.MM, None, -math.inf, "research 22, Scope (no default, ours)"),
    _declare("z_bottom_mm", Unit.MM, None, -math.inf, "research 22, Scope"),
    _STEPDOWN,
    _declare("cut_feed_mm_per_min", Unit.MM_PER_MIN, None, 0.0, "D-025; research 22, Parameters"),
    _declare("plunge_feed_mm_per_min", Unit.MM_PER_MIN, None, 0.0, "D-025; research 22"),
    _AIR_GAP,
)  # REQ-PRF-001, in this order


@dataclass(frozen=True, slots=True)
class ProfileInput:
    """What `job` hands the profile for one operation (AQ-014): the part, the operation's tool,
    the stock and the operation as `check_job` returned it."""

    contour: CurveRows  # one closed loop of material (io's `DxfContour.loop`)
    tool: FlatEndMill
    stock: StockBox
    operation: Operation


@dataclass(frozen=True, slots=True)
class Values:  # the operation's parameters by name (REQ-PRF-001)
    allowance_mm: float
    z_top_mm: float
    z_bottom_mm: float
    stepdown_mm: float
    cut_feed_mm_per_min: float
    plunge_feed_mm_per_min: float
    air_gap_ratio: float
