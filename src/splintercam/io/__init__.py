# SPDX-License-Identifier: Apache-2.0
"""io: file import. Reads a DXF drawing into one closed contour of curve rows (see SPEC.md)."""

from ._read import DxfContour, decode_source_id, read_dxf_contour
from ._units import DrawingUnit

__all__ = [
    "DrawingUnit",
    "DxfContour",
    "decode_source_id",
    "read_dxf_contour",
]
