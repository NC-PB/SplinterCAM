# SPDX-License-Identifier: Apache-2.0
"""geometry2d: planar curves, exact signs and the algorithms on them (see SPEC.md)."""

from ._curves import Arc, Curve, Line, Point, make_arc, make_line
from ._predicates import are_parallel

__all__ = [
    "Arc",
    "Curve",
    "Line",
    "Point",
    "are_parallel",
    "make_arc",
    "make_line",
]
