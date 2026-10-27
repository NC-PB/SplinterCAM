# SPDX-License-Identifier: Apache-2.0
"""The header's ranges (REQ-CL-017), field by field in the order of `ClHeader` (REQ-CL-020)."""

import math
import re

from ._types import ClHeader

# model's operation name, REQ-MDL-012: ASCII letters, digits and underscores.
_NAME = re.compile(r"[A-Za-z0-9_]+")
# DEC-CL-005: a control character breaks the NCX line, `"` ends its quoted string.
_NOT_IN_NOTE = re.compile(r'[\x00-\x1f\x7f"]')


def _positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


def _feeds_valid(feed_classes: tuple[tuple[str, float], ...]) -> bool:
    names = [name for name, _ in feed_classes]
    unique = len(set(names)) == len(names)
    return unique and all(names) and all(_positive(feed) for _, feed in feed_classes)


def header_breach(header: ClHeader) -> str | None:
    """The first field of `header` outside its range, or None."""
    valid = {
        "name": _NAME.fullmatch(header.name) is not None,
        "note": not any(_NOT_IN_NOTE.search(line) for line in header.note),
        "tool_number": header.tool_number >= 1,
        "point_number": header.point_number >= 1,
        "axial_offset_mm": math.isfinite(header.axial_offset_mm) and header.axial_offset_mm >= 0,
        "spindle_rpm": _positive(header.spindle_rpm),
        "tol_mm": _positive(header.tol_mm),
        "feed_classes": _feeds_valid(header.feed_classes),
        "clearance_height_mm": math.isfinite(header.clearance_height_mm),
    }
    return next((field for field, ok in valid.items() if not ok), None)
