# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the operation header and the order of the checks (REQ-CL-002, 017, 020)."""

import math
from dataclasses import replace

import pytest

from cl_strategies import (
    HEADER,
    NAN,
    changed,
    columns,
    profile_moves,
    refusal,
)
from splintercam.cl import ClHeader, Role, make_operation
from splintercam.foundation import Context

_TIMES = chr(0xD7)  # the multiplication sign of the SPEC's example note (Example parts)


@pytest.mark.req("REQ-CL-002")
def test_every_header_field_reads_back(ctx: Context) -> None:
    header = ClHeader(
        name="Outside_Profile_2",
        note=(f"Rohteil 105 {_TIMES} 65", "Spannung: Schraubstock"),
        tool_number=12,
        point_number=1,
        axial_offset_mm=0.5,
        spindle_rpm=12000.0,
        tol_mm=0.02,
        feed_classes=(("plunge", 250.0), ("cut", 1200.0), ("lead", 600.0)),
        clearance_height_mm=4.5,  # the record's moves at h_c = 5 lie above it
    )
    held = make_operation(header, columns(profile_moves()), ctx).header
    assert (held.name, held.note) == ("Outside_Profile_2", header.note)
    assert (held.tool_number, held.point_number, held.axial_offset_mm) == (12, 1, 0.5)
    assert (held.spindle_rpm, held.tol_mm, held.clearance_height_mm) == (12000.0, 0.02, 4.5)
    assert held.feed_classes == (("plunge", 250.0), ("cut", 1200.0), ("lead", 600.0))


# One wrong value per field, in the order of `ClHeader` (REQ-CL-020).
_BROKEN: list[tuple[str, object]] = [
    ("name", ""),
    ("name", "Profil 1"),
    ("name", "Profil-1"),
    ("name", "Fräsen"),
    ("note", ("ok", "line\nbreak")),
    ("note", ("tab\there",)),
    ("note", ("delete\x7f",)),
    ("note", ('say "hi"',)),
    ("tool_number", 0),
    ("point_number", 0),
    ("axial_offset_mm", -0.1),
    ("axial_offset_mm", NAN),
    ("axial_offset_mm", math.inf),
    ("spindle_rpm", 0.0),
    ("spindle_rpm", math.inf),
    ("tol_mm", -0.01),
    ("tol_mm", NAN),
    ("feed_classes", (("plunge", 300.0), ("cut", 0.0))),
    ("feed_classes", (("plunge", 300.0), ("cut", NAN))),
    ("feed_classes", (("plunge", 300.0), ("", 1000.0))),
    ("feed_classes", (("cut", 300.0), ("cut", 1000.0))),
    ("clearance_height_mm", NAN),
    ("clearance_height_mm", -math.inf),
]


@pytest.mark.req("REQ-CL-017", "REQ-CL-020")
@pytest.mark.parametrize(("field", "value"), _BROKEN)
def test_a_header_field_out_of_range_is_refused(field: str, value: object, ctx: Context) -> None:
    header = replace(HEADER, **{field: value})
    name = header.name if field == "name" else HEADER.name
    pattern = refusal("REQ-CL-017", name=name) + f": header field {field}"
    with pytest.raises(ValueError, match=pattern):
        make_operation(header, columns(profile_moves()), ctx)


@pytest.mark.req("REQ-CL-017")
def test_a_note_with_umlauts_and_signs_passes(ctx: Context) -> None:
    header = replace(HEADER, note=(f"Rohteil 105 {_TIMES} 65", "Ø 10, Außenkontur", ""))
    assert make_operation(header, columns(profile_moves()), ctx).header.note == header.note


@pytest.mark.req("REQ-CL-020")
def test_a_broken_header_is_named_before_a_broken_move(ctx: Context) -> None:
    moves = changed(columns(profile_moves()), "end_mm", (5, 0), NAN)
    with pytest.raises(ValueError, match=refusal("REQ-CL-017") + ": header field tol_mm"):
        make_operation(replace(HEADER, tol_mm=0.0), moves, ctx)


@pytest.mark.req("REQ-CL-020")
def test_the_lower_requirement_is_named_first(ctx: Context) -> None:
    # Move 4 is a LINE given role LINK (REQ-CL-005) and a missing feed class (REQ-CL-009).
    moves = changed(columns(profile_moves()), "role", 4, Role.LINK)
    moves = changed(moves, "feed_class", 4, 7)
    with pytest.raises(ValueError, match=refusal("REQ-CL-005", 4)):
        make_operation(HEADER, moves, ctx)


@pytest.mark.req("REQ-CL-020")
def test_the_first_breaking_move_is_named(ctx: Context) -> None:
    moves = changed(columns(profile_moves()), "end_mm", (20, 1), NAN)
    moves = changed(moves, "end_mm", (9, 0), math.inf)
    with pytest.raises(ValueError, match=refusal("REQ-CL-007", 9)):
        make_operation(HEADER, moves, ctx)
