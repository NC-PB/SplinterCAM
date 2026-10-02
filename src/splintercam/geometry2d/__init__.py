# SPDX-License-Identifier: Apache-2.0
"""geometry2d: planar curves, exact signs and the algorithms on them (see SPEC.md)."""

from ._box import Box, bounding_box
from ._bulge import arc_from_bulge, bulges_from_arc
from ._curves import Arc, Curve, Line, Point, make_arc, make_line
from ._flatten import AirSide, flatten
from ._predicates import are_parallel
from ._rows import CurveRows, curve_rows

__all__ = [
    "AirSide",
    "Arc",
    "Box",
    "Curve",
    "CurveRows",
    "Line",
    "Point",
    "arc_from_bulge",
    "are_parallel",
    "bounding_box",
    "bulges_from_arc",
    "curve_rows",
    "flatten",
    "make_arc",
    "make_line",
]
