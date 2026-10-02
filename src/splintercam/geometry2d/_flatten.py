# SPDX-License-Identifier: Apache-2.0
"""Flattening with a known error side (research 01, Flattening with a known error side)."""

import enum
import math

import numpy as np
from numpy.typing import NDArray

from splintercam import _kernels
from splintercam.foundation import TOLERANCE_DEFAULTS, Context

from ._curves import Arc, Curve, Line

# π/2, a declared parameter (REQ-G2D-230), passed to the kernel as a plain value.
_MAX_STEP_RAD = TOLERANCE_DEFAULTS["flatten_step_max_rad"].default


class AirSide(enum.Enum):
    """Where air lies, seen along the curve."""

    LEFT = enum.auto()
    RIGHT = enum.auto()


def flatten(curve: Curve, t_mm: float, side: AirSide | None, ctx: Context) -> NDArray[np.float64]:
    """The curve as a read-only (n, 2) polyline from P0 to P1, both bit for bit, within `t_mm`.

    An arc is flattened inscribed when its centre lies on the air side (left of the arc for a
    positive sweep) or no side is given, circumscribed otherwise. A non-positive or non-finite
    `t_mm` is a programming error, `ValueError`. Expects a curve from `make_line` or `make_arc`.

    Implements: REQ-G2D-102 to 106, REQ-G2D-109, REQ-G2D-110, REQ-G2D-112, REQ-G2D-113,
    REQ-G2D-126, REQ-G2D-230.
    """
    del ctx  # every public function takes the Context (SPEC, Public interface)
    if not (math.isfinite(t_mm) and t_mm > 0.0):
        raise ValueError(f"t_mm must be finite and > 0, got {t_mm!r}")
    match curve:
        case Line():
            points = np.array([curve.p0, curve.p1], dtype=np.float64)
        case Arc():
            inscribed = side is None or (side is AirSide.LEFT) == (curve.sweep_rad > 0.0)
            row = np.array([[*curve.p0, *curve.p1, *curve.centre, curve.sweep_rad]])
            kernel = _kernels.geometry2d
            steps = kernel.arc_steps(row, t_mm, inscribed, _MAX_STEP_RAD)
            points = np.empty((steps + (1 if inscribed else 2), 2), dtype=np.float64)
            kernel.flatten_arc(row, steps, inscribed, points)
    points.flags.writeable = False
    return points
