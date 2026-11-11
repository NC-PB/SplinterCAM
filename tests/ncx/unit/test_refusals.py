# SPDX-License-Identifier: Apache-2.0
"""What `write_ncx` refuses, and in which order (REQ-NCX-003, 010, 013 to 017, 026)."""

import math
from dataclasses import replace

import numpy as np
import pytest

from cl_strategies import Move, arc, framed, full_circle, profile_moves
from ncx_programs import PROFILE, RECT_FILLETS, exact_text, record, refused, words, written
from splintercam.cl import ClHeader, ClOperation
from splintercam.foundation import Context, Severity
from splintercam.ncx import ProgramInfo, write_ncx
from splintercam.ncx._moves import move_blocks, printed
from splintercam.ncx._refusals import operation_errors


@pytest.mark.req("REQ-NCX-010", "REQ-NCX-013")
def test_a_z_past_the_double_range_is_refused(ctx: Context) -> None:
    # cl checks z and a apart; z + a can overflow to inf, which must not print as Z=0.0.
    operation = record(ctx).operations[0]
    end = operation.moves.end_mm.copy()
    end[:, 2] = 1.5e308
    moves = replace(operation.moves, end_mm=end)
    huge = ClOperation(replace(operation.header, axial_offset_mm=1.5e308), moves)
    columns = printed(huge)
    assert (columns.counts[:, 2] == 0).all()  # masked, never printed from inf
    found = operation_errors("operation 1 (PROFILE_1)", huge, huge.header, columns)
    # a itself is written as TIP_OFFSET and is out of range too, before the moves (DEC-NCX-020).
    assert [d.message.split(":")[0] for d in found] == ["point 1"] + [
        f"move {i}" for i in range(44)
    ]
    assert [d.code for d in found] == ["NCX_VALUE_OUT_OF_RANGE"] * 45


@pytest.mark.req("REQ-NCX-009", "REQ-NCX-017")
def test_a_tol_without_a_tolerance_set_is_reported(ctx: Context) -> None:
    # DEC-NCX-012: cl takes any tol above 0; below 2/875 mm there is no rounding allowance.
    found = refused(ctx, replace(PROFILE, tol_mm=0.001))
    assert [(d.code, d.location) for d in found] == [
        ("TOL_BELOW_MINIMUM", "operation 1 (PROFILE_1)")
    ]


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


@pytest.mark.req("REQ-NCX-010", "REQ-NCX-013")
def test_a_value_of_1e9_is_refused(ctx: Context) -> None:
    # The first move's z = h_c = 5 becomes 1e9 with a = 1e9 - 5; a itself is below 10^9.
    found = refused(ctx, replace(PROFILE, axial_offset_mm=1e9 - 5.0))
    # The moves ending at h_c = 5 reach 1e9; every lower z stays below it.
    at_clearance = [i for i, move in enumerate(profile_moves()) if move.end[2] == 5.0]
    assert {d.location for d in found} == {"operation 1 (PROFILE_1)"}
    assert [d.code for d in found] == ["NCX_VALUE_OUT_OF_RANGE"] * len(at_clearance)
    assert [d.message.split(":")[0] for d in found] == [f"move {i}" for i in at_clearance]
    below = float(np.nextafter(1e9, 0.0))
    # ... and the largest Z below 10^9 is written (REQ-NCX-007), with a as TIP_OFFSET.
    lines = written(ctx, replace(PROFILE, axial_offset_mm=below - 5.0)).text.split("\n")
    first = next(line for line in lines if line.startswith("RAPID"))
    assert words(first)["Z"] == exact_text(5.0 + (below - 5.0))
    (tool,) = (line for line in lines if line.startswith("TOOL="))
    assert words(tool)["TIP_OFFSET"] == exact_text(below - 5.0)
    (operation,) = record(ctx, replace(PROFILE, axial_offset_mm=below - 5.0)).operations
    assert move_blocks(operation, printed(operation))[0] == first


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
@pytest.mark.parametrize("point", [2, 9])
def test_a_point_other_than_1_is_written(ctx: Context, point: int) -> None:
    # Peter, AQ-005 item 4: refused "until NCX has point words"; NCXchange 1e2fd00 has them.
    text = written(ctx, replace(PROFILE, point_number=point)).text
    assert f" TOOL_POINT={point} " in text


@pytest.mark.req("REQ-NCX-013")
@pytest.mark.parametrize(
    ("offset", "tip"), [(5e-324, "0.0"), (1e-6, "0.000001"), (1.0, "1.0"), (40.0, "40.0")]
)
def test_an_axial_offset_other_than_0_is_written(ctx: Context, offset: float, tip: str) -> None:
    # Peter, AQ-035: refused until "D-155's point words exist"; the program now says a.
    lines = written(ctx, replace(PROFILE, axial_offset_mm=offset)).text.split("\n")
    (tool,) = (line for line in lines if line.startswith("TOOL="))
    assert words(tool)["TIP_OFFSET"] == tip


@pytest.mark.req("REQ-NCX-002", "REQ-NCX-008")
@pytest.mark.parametrize(("radius", "text"), [(0.0, "0.0"), (3.0, "3.0"), (2.5e-7, "0.0")])
def test_the_register_radius_is_written(ctx: Context, radius: float, text: str) -> None:
    # Peter, AQ-050: the job's r, from the record, as POINT_RADIUS; compensation stays off.
    lines = written(ctx, replace(PROFILE, register_radius_mm=radius)).text.split("\n")
    (tool,) = (line for line in lines if line.startswith("TOOL="))
    assert words(tool)["POINT_RADIUS"] == text
    assert "COMP=OFF" in lines[2]


@pytest.mark.req("REQ-NCX-010")
def test_a_register_radius_of_1e9_is_refused(ctx: Context) -> None:
    found = refused(ctx, replace(PROFILE, register_radius_mm=1e9))
    assert [(d.code, d.message) for d in found] == [
        ("NCX_VALUE_OUT_OF_RANGE", "point 1: register radius r = 1000000000.0 mm is 10^9 or more")
    ]


@pytest.mark.req("REQ-NCX-003")
@pytest.mark.parametrize(
    ("change", "named"),
    [
        ({"point_number": 2}, "point 2 at a = 0.0 mm, r = 0.0 mm"),
        ({"axial_offset_mm": 1.0}, "point 1 at a = 1.0 mm, r = 0.0 mm"),
        # Compared exactly (DEC-NCX-020 (a)): both print TIP_OFFSET=0.0, yet the Z differ.
        ({"axial_offset_mm": 5e-324}, "point 1 at a = 5e-324 mm, r = 0.0 mm"),
        ({"axial_offset_mm": 2.5e-7}, "point 1 at a = 2.5e-07 mm, r = 0.0 mm"),
        # AQ-050: r belongs to the point too.
        ({"register_radius_mm": 3.0}, "point 1 at a = 0.0 mm, r = 3.0 mm"),
    ],
)
def test_a_change_of_point_is_refused(ctx: Context, change: dict[str, float], named: str) -> None:
    # DEC-NCX-020: one tool block holds the point; a point block without TOOL is unchecked.
    second = replace(PROFILE, name="B", **change)
    found = refused(ctx, PROFILE, second)
    assert [(d.code, d.severity, d.location) for d in found] == [
        ("NCX_POINT_CHANGE_UNSUPPORTED", Severity.ERROR, "operation 2 (B)")
    ]
    assert found[0].message.startswith(named)
    assert "first operation's point 1 at a = 0.0 mm, r = 0.0 mm" in found[0].message
    # The same point in both operations, at any k and a, is written.
    same = replace(PROFILE, point_number=2, axial_offset_mm=1.0, register_radius_mm=3.0)
    written(ctx, same, replace(same, name="B"))
    # -0.0 is the same point as 0.0: it moves no Z (DEC-NCX-018 (b)).
    written(ctx, PROFILE, replace(PROFILE, name="B", axial_offset_mm=-0.0))


@pytest.mark.req("REQ-NCX-003", "REQ-NCX-010", "REQ-NCX-017")
def test_the_point_change_comes_before_the_speed_and_the_offset_out_of_range(
    ctx: Context,
) -> None:
    second = replace(PROFILE, name="B", point_number=2, spindle_rpm=1e9, axial_offset_mm=1e9)
    found = refused(ctx, PROFILE, second)
    above = [index for index, move in enumerate(profile_moves()) if move.end[2] >= 0.0]
    assert [(d.code, d.message.split(":")[0].split(" ")[0]) for d in found] == [
        ("NCX_TOOL_CHANGE_UNSUPPORTED", "tool"),  # the speed differs too
        ("NCX_POINT_CHANGE_UNSUPPORTED", "point"),
        ("NCX_VALUE_OUT_OF_RANGE", "spindle"),
        ("NCX_VALUE_OUT_OF_RANGE", "point"),
        *(("NCX_VALUE_OUT_OF_RANGE", "move") for _ in above),
    ]


@pytest.mark.req("REQ-NCX-003", "REQ-NCX-017")
def test_the_point_change_comes_after_the_tool_change_and_before_the_note_and_the_tol(
    ctx: Context,
) -> None:
    second = replace(PROFILE, name="B", tool_number=2, point_number=2, note=("(a)",), tol_mm=0.001)
    assert [d.code for d in refused(ctx, PROFILE, second)] == [
        "NCX_TOOL_CHANGE_UNSUPPORTED",
        "NCX_POINT_CHANGE_UNSUPPORTED",
        "NCX_NOTE_CHARACTER",
        "TOL_BELOW_MINIMUM",
    ]


@pytest.mark.req("REQ-NCX-013")
def test_a_negative_zero_offset_is_written(ctx: Context) -> None:
    # cl takes a = -0.0 (a ≥ 0); it moves no Z, so it is 0 (DEC-NCX-018 (b)).
    assert written(ctx, replace(PROFILE, axial_offset_mm=-0.0)).text == written(ctx).text


@pytest.mark.req("REQ-NCX-014")
@pytest.mark.parametrize(
    "name",
    ["RECT FILLETS", "con", "Lpt9", "COM1", "COM0", "lpt0", "nul", "", "Rect-1", "Teil_Ä", "A.B"],
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
    # Its chord is below 0.001 mm as well: REQ-NCX-026 after 016 (REQ-NCX-017).
    assert [(d.code, d.location, d.message.split(":")[0]) for d in found] == [
        ("NCX_ARC_PRINTS_DEGENERATE", "operation 1 (PROFILE_1)", "move 4"),
        ("NCX_ARC_CHORD_TOO_SHORT", "operation 1 (PROFILE_1)", "move 4"),
    ]


@pytest.mark.req("REQ-NCX-016")
def test_an_arc_whose_centre_prints_on_its_start_is_refused(ctx: Context) -> None:
    # A half circle of radius about 1.39e-6, above eps_len, so cl accepts it; start and centre
    # both print as (0.0, 0.0), the end as (0.000001, 0.000001).
    start, centre, end = (-4.9e-7, -4.9e-7), (4.9e-7, 4.9e-7), (1.47e-6, 1.47e-6)
    moves = framed(arc((*end, -1.0), centre, math.pi), start)
    found = write_ncx(record(ctx, PROFILE, moves=moves), RECT_FILLETS, ctx).diagnostics
    assert [(d.code, d.message.split(":")[0]) for d in found] == [
        ("NCX_ARC_PRINTS_DEGENERATE", "move 4"),
        ("NCX_ARC_CHORD_TOO_SHORT", "move 4"),
    ]


def _short_arc(chord: float, direction: float) -> list[Move]:
    # An arc of radius 1 about the origin from (1, 0) whose chord is `chord`; cl accepts it.
    sweep = direction * 2.0 * math.asin(chord / 2.0)
    end = (math.cos(sweep), math.sin(sweep), -1.0)
    return framed(arc(end, (0.0, 0.0), sweep), (1.0, 0.0))


@pytest.mark.req("REQ-NCX-026")
@pytest.mark.parametrize("direction", [1.0, -1.0])
def test_an_arc_with_a_chord_below_the_machine_step_is_refused(
    ctx: Context, direction: float
) -> None:
    found = write_ncx(record(ctx, PROFILE, moves=_short_arc(0.0009, direction)), RECT_FILLETS, ctx)
    assert found.value is None
    assert [(d.code, d.location, d.message.split(":")[0]) for d in found.diagnostics] == [
        ("NCX_ARC_CHORD_TOO_SHORT", "operation 1 (PROFILE_1)", "move 4")
    ]
    written(ctx, PROFILE, moves=_short_arc(0.0011, direction))


@pytest.mark.req("REQ-NCX-026")
def test_a_full_circle_has_no_chord_to_refuse(ctx: Context) -> None:
    written(ctx, PROFILE, moves=full_circle(math.tau))


@pytest.mark.req("REQ-NCX-013", "REQ-NCX-017", "REQ-NCX-026")
def test_the_arc_errors_come_by_id_and_the_tol_last(ctx: Context) -> None:
    header = replace(PROFILE, point_number=2, tol_mm=0.001)
    start, end, centre = (-4.9e-7, -4.9e-7), (4.9e-7, 4.9e-7), (10.0, -10.0)
    sweep = math.atan2(end[1] - centre[1], end[0] - centre[0]) - math.atan2(
        start[1] - centre[1], start[0] - centre[0]
    )
    moves = framed(arc((*end, -1.0), centre, sweep), start)
    found = write_ncx(record(ctx, header, moves=moves), RECT_FILLETS, ctx).diagnostics
    assert [d.code for d in found] == [  # point 2 is no error (REQ-NCX-013)
        "NCX_ARC_PRINTS_DEGENERATE",
        "NCX_ARC_CHORD_TOO_SHORT",
        "TOL_BELOW_MINIMUM",
    ]


@pytest.mark.req("REQ-NCX-003", "REQ-NCX-017")
def test_every_error_is_reported_in_order(ctx: Context) -> None:
    first = replace(PROFILE, point_number=3, note=("(a)",))
    second = replace(PROFILE, name="B", tool_number=2, point_number=2, note=("\\",))
    program = ProgramInfo("con", 0)
    assert _codes(ctx, first, second, program=program) == [
        ("NCX_PROGRAM_NAME_INVALID", "program"),
        ("NCX_PROGRAM_NUMBER_INVALID", "program"),
        ("NCX_NOTE_CHARACTER", "operation 1 (PROFILE_1)"),
        ("NCX_TOOL_CHANGE_UNSUPPORTED", "operation 2 (B)"),
        ("NCX_POINT_CHANGE_UNSUPPORTED", "operation 2 (B)"),
        ("NCX_NOTE_CHARACTER", "operation 2 (B)"),
    ]


@pytest.mark.req("REQ-NCX-010", "REQ-NCX-013", "REQ-NCX-017")
def test_moves_out_of_range_are_named_by_index(ctx: Context) -> None:
    # With a = 1e9, a itself (TIP_OFFSET) comes first, then every move at or above z = 0 (the
    # rapids), which reaches 1e9, in move order (DEC-NCX-020).
    found = refused(ctx, replace(PROFILE, axial_offset_mm=1e9))
    above = [index for index, move in enumerate(profile_moves()) if move.end[2] >= 0.0]
    assert len(above) == 8
    assert [d.message.split(":")[0] for d in found] == ["point 1"] + [
        f"move {index}" for index in above
    ]
    assert {d.code for d in found} == {"NCX_VALUE_OUT_OF_RANGE"}
    assert found[0].message == "point 1: axial offset a = 1000000000.0 mm is 10^9 or more"
