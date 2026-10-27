# SPDX-License-Identifier: Apache-2.0
"""The header's ranges (REQ-CL-017), field by field in the order of `ClHeader` (REQ-CL-020)."""

import math
import re
from collections.abc import Callable

from ._types import ClHeader

# model's operation name, REQ-MDL-012: ASCII letters, digits and underscores.
_NAME = re.compile(r"[A-Za-z0-9_]+")
# DEC-CL-005: a control character breaks the NCX line, `"` ends its quoted string.
_NOT_IN_NOTE = re.compile(r'[\x00-\x1f\x7f"]')


def _positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


# Lazy, so a later field of the wrong type cannot hide an earlier field's refusal.
_VALID: tuple[tuple[str, Callable[[ClHeader], bool]], ...] = (
    ("name", lambda h: _NAME.fullmatch(h.name) is not None),
    ("note", lambda h: not any(_NOT_IN_NOTE.search(line) for line in h.note)),
    ("tool_number", lambda h: h.tool_number >= 1),
    ("point_number", lambda h: h.point_number >= 1),
    ("axial_offset_mm", lambda h: math.isfinite(h.axial_offset_mm) and h.axial_offset_mm >= 0),
    ("spindle_rpm", lambda h: _positive(h.spindle_rpm)),
    ("tol_mm", lambda h: _positive(h.tol_mm)),
    ("feed_classes", lambda h: len({name for name, _ in h.feed_classes}) == len(h.feed_classes)
     and all(name and _positive(feed) for name, feed in h.feed_classes)),
    ("clearance_height_mm", lambda h: math.isfinite(h.clearance_height_mm)),
)  # fmt: skip


def header_breach(header: ClHeader) -> str | None:
    # The first field of `header` outside its range, or None.
    return next((field for field, valid in _VALID if not valid(header)), None)
