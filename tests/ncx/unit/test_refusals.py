# SPDX-License-Identifier: Apache-2.0
"""What `write_ncx` refuses, and in which order (REQ-NCX-003, 010, 013 to 017)."""

import math
from dataclasses import replace

import numpy as np
import pytest

from cl_strategies import arc, framed, profile_moves
from ncx_programs import PROFILE, RECT_FILLETS, record, refused, written
from splintercam.cl import ClHeader
from splintercam.foundation import Context, Severity
from splintercam.ncx import ProgramInfo, write_ncx


def _codes(
    ctx: Context, *headers: ClHeader, program: ProgramInfo = RECT_FILLETS
) -> list[tuple[str, str | None]]:
    found = refused(ctx, *headers, program=program)
    assert all(d.severity is Severity.ERROR for d in found)
    return [(d.code, d.location) for d in found]


@pytest.mark.req("REQ-NCX-003")
@pytest.mark.parametrize("change", [{"tool_number": 2}, {"spindle_rpm": 9000.0}])
def test_a_second_tool_or_speed_is_refused(ctx: Context, change: dict[str, float]) -> None:
    second = replace(PROFILE, name="B", **change)
    assert _codes(ctx, PROFILE, second) == [("NCX_TOOL_CHANGE_UNSUPPORTED", "operation 2 (B)")]


@pytest.mark.req("REQ-NCX-010")
def test_a_value_of_1e9_is_refused(ctx: Context) -> None:
    # The first move's z = h_c = 5 becomes 1e9 with a = 1e9 - 5.
    found = refused(ctx, replace(PROFILE, axial_offset_mm=1e9 - 5.0))
    assert [d.code for d in found][:1] == ["NCX_VALUE_OUT_OF_RANGE"]
    assert "move 0" in found[0].message
    assert found[0].location == "operation 1 (PROFILE_1)"
    below = float(np.nextafter(1e9, 0.0))
    written(ctx, replace(PROFILE, axial_offset_mm=below - 5.0))


@pytest.mark.req("REQ-NCX-010")
def test_a_feed_of_1e9_is_refused(ctx: Context) -> None:
    feeds = (("plunge", 300.0), ("cut", 1e9))
    found = refused(ctx, replace(PROFILE, feed_classes=feeds))
    assert {d.code for d in found} == {"NCX_VALUE_OUT_OF_RANGE"}
    assert "move 5:" in found[0].message  # the first CUT move
    below = float(np.nextafter(1e9, 0.0))
    written(ctx, replace(PROFILE, feed_classes=(("plunge", 300.0), ("cut", below))))


@pytest.mark.req("REQ-NCX-010")
def test_a_speed_of_1e9_is_refused(ctx: Context) -> None:
    assert _codes(ctx, replace(PROFILE, spindle_rpm=1e9)) == [
        ("NCX_VALUE_OUT_OF_RANGE", "operation 1 (PROFILE_1)")
    ]


@pytest.mark.req("REQ-NCX-013")
def test_a_point_other_than_1_is_refused(ctx: Context) -> None:
    found = refused(ctx, replace(PROFILE, point_number=2))
    assert [d.code for d in found] == ["NCX_POINT_UNSUPPORTED"]
    assert "2" in found[0].message


@pytest.mark.req("REQ-NCX-014")
@pytest.mark.parametrize(
    "name", ["RECT FILLETS", "con", "Lpt9", "COM1", "nul", "", "Rect-1", "Teil_Ä", "A.B"]
)
def test_an_invalid_program_name_is_refused(ctx: Context, name: str) -> None:
    program = ProgramInfo(name, 1001)
    assert _codes(ctx, PROFILE, program=program) == [("NCX_PROGRAM_NAME_INVALID", "program")]


@pytest.mark.req("REQ-NCX-014")
@pytest.mark.parametrize("name", ["CONSOLE", "COM10", "LPT", "Con_1", "x"])
def test_names_near_the_device_names_pass(ctx: Context, name: str) -> None:
    assert write_ncx(record(ctx), ProgramInfo(name, 1), ctx).ok


@pytest.mark.req("REQ-NCX-014")
@pytest.mark.parametrize("number", [0, -1])
def test_a_program_number_below_1_is_refused(ctx: Context, number: int) -> None:
    program = ProgramInfo("RECT_FILLETS", number)
    assert _codes(ctx, PROFILE, program=program) == [("NCX_PROGRAM_NUMBER_INVALID", "program")]


@pytest.mark.req("REQ-NCX-015")
@pytest.mark.parametrize(
    ("line", "character"),
    [
        ("Spannung (oben)", "("),
        ("oben)", ")"),
        ("C:\\Teile", "\\"),
        ("Rohteil 105 \u00d7 65", "\u00d7"),
    ],
)
def test_a_note_character_is_refused(ctx: Context, line: str, character: str) -> None:
    found = refused(ctx, replace(PROFILE, note=("Rohteil", line)))
    assert [(d.code, d.location) for d in found] == [
        ("NCX_NOTE_CHARACTER", "operation 1 (PROFILE_1)")
    ]
    assert "line 2" in found[0].message
    assert repr(character) in found[0].message


@pytest.mark.req("REQ-NCX-016")
def test_an_arc_that_prints_degenerate_is_refused(ctx: Context) -> None:
    # More than eps_len between the ends, so cl accepts it; both ends print as (0.0, 0.0).
    start, end, centre = (-4.9e-7, -4.9e-7), (4.9e-7, 4.9e-7), (10.0, -10.0)
    sweep = math.atan2(end[1] - centre[1], end[0] - centre[0]) - math.atan2(
        start[1] - centre[1], start[0] - centre[0]
    )
    moves = framed(arc((*end, -1.0), centre, sweep), start)
    data = record(ctx, PROFILE, moves=moves)
    found = write_ncx(data, RECT_FILLETS, ctx).diagnostics
    assert [(d.code, d.location) for d in found] == [
        ("NCX_ARC_PRINTS_DEGENERATE", "operation 1 (PROFILE_1)")
    ]
    assert "move 4" in found[0].message


@pytest.mark.req("REQ-NCX-017")
def test_every_error_is_reported_in_order(ctx: Context) -> None:
    first = replace(PROFILE, point_number=3, note=("(a)",))
    second = replace(PROFILE, name="B", tool_number=2, point_number=2, note=("\\",))
    program = ProgramInfo("con", 0)
    assert _codes(ctx, first, second, program=program) == [
        ("NCX_PROGRAM_NAME_INVALID", "program"),
        ("NCX_PROGRAM_NUMBER_INVALID", "program"),
        ("NCX_POINT_UNSUPPORTED", "operation 1 (PROFILE_1)"),
        ("NCX_NOTE_CHARACTER", "operation 1 (PROFILE_1)"),
        ("NCX_TOOL_CHANGE_UNSUPPORTED", "operation 2 (B)"),
        ("NCX_POINT_UNSUPPORTED", "operation 2 (B)"),
        ("NCX_NOTE_CHARACTER", "operation 2 (B)"),
    ]


@pytest.mark.req("REQ-NCX-010", "REQ-NCX-017")
def test_moves_out_of_range_are_named_by_index(ctx: Context) -> None:
    # With a = 1e9 every move at or above z = 0 (the rapids) reaches 1e9, in move order.
    found = refused(ctx, replace(PROFILE, axial_offset_mm=1e9))
    above = [index for index, move in enumerate(profile_moves()) if move.end[2] >= 0.0]
    assert len(above) == 8
    assert [d.message.split(":")[0] for d in found] == [f"move {index}" for index in above]
