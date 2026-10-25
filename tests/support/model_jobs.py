# SPDX-License-Identifier: Apache-2.0
"""The model SPEC's example job (plan 0007's job) and research 22's profile declarations, shared by
the model unit and property tests."""

import logging
import math

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import TOLERANCE_DEFAULTS, CancellationToken, Context, ToleranceSet
from splintercam.model import (
    FlatEndMill,
    JobData,
    Operation,
    ParameterDeclaration,
    Setup,
    StockBox,
    Unit,
)


class _NullSink:
    def add(self, name: str, kind: str, data: NDArray[np.float64]) -> None:
        del name, kind, data


def make_context() -> Context:
    """A fresh `Context` with the finishing default tolerance (Hypothesis cannot use fixtures)."""
    built = ToleranceSet.for_operation(TOLERANCE_DEFAULTS["chord_tol_finishing_mm"].default)
    assert built.value is not None
    return Context(built.value, CancellationToken(), lambda _f: None,
                   logging.getLogger("model.tests"), _NullSink(), 0)  # fmt: skip


def declaration(name: str, unit: Unit, default: float | None, low: float = 0.0,
                low_open: bool = False) -> ParameterDeclaration:  # fmt: skip
    """A declaration open to +inf, cited to research 22, Parameters."""
    return ParameterDeclaration(name, unit, default, low, math.inf, low_open, True,
                                "research 22, Parameters")  # fmt: skip


# The slice's profile parameters (research 22, Parameters): step-down and feeds have no default.
PROFILE = (
    declaration("allowance_mm", Unit.MM, 0.0, -math.inf),
    declaration("z_top_mm", Unit.MM, 0.0, -math.inf),
    declaration("z_bottom_mm", Unit.MM, None, -math.inf),
    declaration("step_down_mm", Unit.MM, None, low_open=True),
    declaration("cut_feed_mm_per_min", Unit.MM_PER_MIN, None, low_open=True),
    declaration("plunge_feed_mm_per_min", Unit.MM_PER_MIN, None, low_open=True),
    declaration("air_gap_ratio", Unit.RATIO, 0.2),
)
DECLARATIONS = {"profile": PROFILE}

PARAMETERS = (
    ("allowance_mm", 0.0),
    ("z_top_mm", 0.0),
    ("z_bottom_mm", -10.0),
    ("step_down_mm", 4.0),
    ("cut_feed_mm_per_min", 1200.0),
    ("plunge_feed_mm_per_min", 300.0),
)


def operation(name: str = "PROFILE_1", parameters: tuple[tuple[str, float], ...] = PARAMETERS
              ) -> Operation:  # fmt: skip
    return Operation(name, "profile", 1, 8000.0, 0.01, parameters)


def example_job(operations: tuple[Operation, ...] | None = None) -> JobData:
    """T1, D 10 with 30 mm of flute at the tip; the stock 5 mm round the 100 x 60 rectangle of
    research 22 test 1, top at z 0; work offset 1 (model SPEC, Example parts)."""
    tool = FlatEndMill(1, 10.0, 30.0)
    stock = StockBox((-5.0, -5.0, -20.0), (105.0, 65.0, 0.0))
    return JobData((tool,), Setup(1, stock, operations or (operation(),)))
