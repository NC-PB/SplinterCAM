# SPDX-License-Identifier: Apache-2.0
"""The profile's declared parameters, its typed input and the values read from an operation
(research 22, Parameters; D-049; AQ-014)."""

import math
from dataclasses import dataclass

from splintercam.geometry2d import CurveRows
from splintercam.model import FlatEndMill, Operation, ParameterDeclaration, StockBox, Unit

STRATEGY_ID = "profile"


def _declare(name: str, unit: Unit, default: float | None, low: float, source: str
             ) -> ParameterDeclaration:  # fmt: skip
    # Open to +inf; open at a finite low end (> 0), closed at -inf (any finite value).
    return ParameterDeclaration(name, unit, default, low, math.inf, math.isfinite(low), True,
                                source)  # fmt: skip


_ANY = -math.inf
DECLARATIONS: tuple[ParameterDeclaration, ...] = (
    _declare("allowance_mm", Unit.MM, 0.0, _ANY, "D-150; research 22, Parameters"),
    _declare("z_top_mm", Unit.MM, None, _ANY, "research 22, Scope (no default, ours)"),
    _declare("z_bottom_mm", Unit.MM, None, _ANY, "research 22, Scope"),
    _declare("stepdown_mm", Unit.MM, None, 0.0, "research 22, Parameters"),
    _declare("cut_feed_mm_per_min", Unit.MM_PER_MIN, None, 0.0, "D-025; research 22, Parameters"),
    _declare("plunge_feed_mm_per_min", Unit.MM_PER_MIN, None, 0.0, "D-025; research 22"),
    _declare("air_gap_ratio", Unit.RATIO, 0.2, 0.0, "D-079; research 22, Parameters"),
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
class Values:
    """The operation's parameters by name, in mm and mm/min (REQ-PRF-001)."""

    allowance_mm: float
    z_top_mm: float
    z_bottom_mm: float
    stepdown_mm: float
    cut_feed_mm_per_min: float
    plunge_feed_mm_per_min: float
    air_gap_ratio: float
