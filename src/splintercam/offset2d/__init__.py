# SPDX-License-Identifier: Apache-2.0
"""offset2d: offsets and Booleans of machining regions on Clipper2's grid (see SPEC.md)."""

from ._classes import EdgeClass, SourceClasses
from ._region import offset_region

__all__ = ["EdgeClass", "SourceClasses", "offset_region"]
