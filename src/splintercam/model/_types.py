# SPDX-License-Identifier: Apache-2.0
"""The job's data types and the parameter declaration (model SPEC, REQ-MDL-001, 007, 009, 011,
017, 018). The values accept anything; `check_job` checks them where they enter (DEC-MDL-003)."""

import math
from dataclasses import dataclass
from enum import Enum
from typing import cast


@dataclass(frozen=True, slots=True)
class MeasurementPoint:
    """A tool's measurement point k, a mm above the tip along the axis, register radius r mm
    (D-154, D-155). Implements: REQ-MDL-001."""

    number: int
    axial_offset_mm: float
    register_radius_mm: float


TIP = MeasurementPoint(1, 0.0, 0.0)
"""The tip, the slice's point and every tool's default (research 26 subset)."""


@dataclass(frozen=True, slots=True)
class FlatEndMill:
    """A flat end mill entered by hand: its T number, diameter and flute length in mm, and its
    measurement points numbered 1 to n (research 22, Scope; D-154). Implements: REQ-MDL-001."""

    number: int
    diameter_mm: float
    flute_length_mm: float
    points: tuple[MeasurementPoint, ...] = (TIP,)

    @property
    def radius_mm(self) -> float:
        """R, half the diameter, in mm."""
        return self.diameter_mm / 2.0


@dataclass(frozen=True, slots=True)
class StockBox:
    """The stock, an axis-aligned box in the work frame by two corners in mm (D-026).
    Implements: REQ-MDL-007."""

    min_mm: tuple[float, float, float]
    max_mm: tuple[float, float, float]

    @property
    def top_mm(self) -> float:
        """The stock top, the largest z (research 10, Method)."""
        return self.max_mm[2]


class Unit(Enum):
    """A parameter's unit (D-028). Implements: REQ-MDL-017."""

    MM = "mm"
    MM_PER_MIN = "mm/min"
    RATIO = "1"


@dataclass(frozen=True, slots=True)
class ParameterDeclaration:
    """One parameter a strategy declares: name, unit, default (None: the job must give it), a range
    whose ends are each open or closed and may be infinite, and its source (D-018, D-049).

    A declaration is code: an invalid one raises `ValueError` (REQ-MDL-018).
    Implements: REQ-MDL-017, REQ-MDL-018."""

    name: str
    unit: Unit
    default: float | None
    low: float
    high: float
    low_open: bool
    high_open: bool
    source: str

    def __post_init__(self) -> None:
        one_finite = self.low < self.high or (
            self.low == self.high
            and math.isfinite(self.low)
            and not (self.low_open or self.high_open)
        )
        default_ok = self.default is None or in_range(self.default, self)
        # Typed fields, but a strategy can still pass a str unit; REQ-MDL-018 refuses it.
        name, unit, source = cast(
            "tuple[object, object, object]", (self.name, self.unit, self.source)
        )
        checks = (
            (isinstance(name, str) and name.isidentifier(), "name not an identifier"),
            (isinstance(unit, Unit), "unit not a Unit"),
            (isinstance(source, str) and source != "", "source empty"),
            (not (math.isnan(self.low) or math.isnan(self.high)), "an end of the range is NaN"),
            (one_finite, f"the range {range_text(self)} holds no finite value"),
            (default_ok, f"default {self.default!r} not finite or outside {range_text(self)}"),
        )
        for ok, problem in checks:
            if not ok:
                raise ValueError(f"parameter declaration {self.name!r}: {problem}")


def in_range(value: float, declaration: ParameterDeclaration) -> bool:
    """Whether `value` is finite and lies in the declared range, each end open or closed."""
    low, high = declaration.low, declaration.high
    above = value > low if declaration.low_open else value >= low
    below = value < high if declaration.high_open else value <= high
    return math.isfinite(value) and above and below


def range_text(declaration: ParameterDeclaration) -> str:
    """The range as "(0, inf)" or "[0, 1]", for messages (REQ-MDL-023)."""
    left = "(" if declaration.low_open else "["
    right = ")" if declaration.high_open else "]"
    return f"{left}{declaration.low:g}, {declaration.high:g}{right}"


@dataclass(frozen=True, slots=True)
class Operation:
    """An operation: its name (NCX SECTION), strategy id, tool and point, spindle speed in 1/min
    (clockwise, DEC-MDL-006), tolerance tol in mm and (name, value) pairs in the declared units
    (D-052). Implements: REQ-MDL-011."""

    name: str
    strategy: str
    tool_number: int
    spindle_rpm: float
    tol_mm: float
    parameters: tuple[tuple[str, float], ...]
    point_number: int = 1


@dataclass(frozen=True, slots=True)
class Setup:
    """The setup: its work offset (an index, not a G code), its stock and its operations in the
    user's order; the work frame is the drawing's frame (D-078, D-126, DEC-MDL-002).
    Implements: REQ-MDL-009."""

    work_offset: int
    stock: StockBox
    operations: tuple[Operation, ...]


@dataclass(frozen=True, slots=True)
class JobData:
    """What a job knows before anything is computed: its tools and its setup."""

    tools: tuple[FlatEndMill, ...]
    setup: Setup
