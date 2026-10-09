# SPDX-License-Identifier: Apache-2.0
"""offset2d: offsets and Booleans of machining regions on Clipper2's grid (see SPEC.md)."""

from ._boolean import BooleanOp, boolean
from ._chain import grow_chain
from ._classes import EdgeClass, SourceClasses
from ._region import offset_region
from ._stock import machined_area, stock_layer

__all__ = [
    "BooleanOp",
    "EdgeClass",
    "SourceClasses",
    "boolean",
    "grow_chain",
    "machined_area",
    "offset_region",
    "stock_layer",
]
