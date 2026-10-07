# SPDX-License-Identifier: Apache-2.0
"""geometry2d: planar curves, exact signs and the algorithms on them (see SPEC.md)."""

from ._area import signed_area
from ._box import Box, bounding_box
from ._bulge import arc_from_bulge, bulges_from_arc
from ._circle import Circle, circle_through
from ._cleanup import cleanup
from ._curves import Arc, Curve, Line, Point, make_arc, make_line
from ._distances import ClosestPoint, closest_point
from ._flatten import AirSide, flatten
from ._loops import LoopTree, flatten_loops
from ._polygon import FlatRegion, PolygonRegion, RegionKind, polygon_region
from ._predicates import are_parallel, in_arc_circle, incircle, orient2d
from ._region import PointLocation, point_in_region
from ._rows import CurveRows, curve_rows

__all__ = [
    "AirSide",
    "Arc",
    "Box",
    "Circle",
    "ClosestPoint",
    "Curve",
    "CurveRows",
    "FlatRegion",
    "Line",
    "LoopTree",
    "Point",
    "PointLocation",
    "PolygonRegion",
    "RegionKind",
    "arc_from_bulge",
    "are_parallel",
    "bounding_box",
    "bulges_from_arc",
    "circle_through",
    "cleanup",
    "closest_point",
    "curve_rows",
    "flatten",
    "flatten_loops",
    "in_arc_circle",
    "incircle",
    "make_arc",
    "make_line",
    "orient2d",
    "point_in_region",
    "polygon_region",
    "signed_area",
]
