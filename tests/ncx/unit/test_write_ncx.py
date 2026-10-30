# SPDX-License-Identifier: Apache-2.0
"""The NCX text of valid records (REQ-NCX-001 to 009, 012; src/splintercam/ncx/SPEC.md, Example
parts)."""

import inspect
import math
from dataclasses import replace

import pytest

from cl_strategies import full_circle
from ncx_programs import PROFILE, RECT_FILLETS, record, words, written
from splintercam.foundation import Context, ToleranceSet
from splintercam.ncx import write_ncx
from splintercam.ncx._moves import move_blocks, printed

_START = [
    "FILE=BEGIN NCX=1",
    'PROGRAM=BEGIN NAME="RECT_FILLETS" NUMBER=1001',
    "FEED_MODE=PER_MIN COMP=OFF UNITS=MM WORKPLANE=XY CYCLE=OFF",
    "ORIGIN=1",
    'SECTION="PROFILE_1"',
    "TOOL=1 OFFSET:LEN=1 RPM=8000.0 SPINDLE=CW",
    "COOLANT=ON",
    "RAPID Z=5.0",
    "RAPID X=50.0 Y=-15.0 Z=5.0",
    "RAPID X=50.0 Y=-15.0 Z=3.0",
    "LINE X=50.0 Y=-15.0 Z=-3.333333 F=300.0",
    "LINE X=50.0 Y=-5.0 Z=-3.333333",
    "LINE X=5.0 Y=-5.0 Z=-3.333333 F=1200.0",
    "ARC=CW X=-5.0 Y=5.0 Z=-3.333333 CENTER:X=5.0 CENTER:Y=5.0",
]
_END = [
    "LINE X=50.0 Y=-15.0 Z=-10.0",
    "RAPID X=50.0 Y=-15.0 Z=5.0",
    "COOLANT=OFF",
    "SPINDLE=OFF",
    "PROGRAM=END",
    "FILE=END",
]


@pytest.mark.req("REQ-NCX-001", "REQ-NCX-002", "REQ-NCX-005", "REQ-NCX-006")
def test_research_22_test_1_in_order(ctx: Context) -> None:
    program = written(ctx)
    lines = program.text.split("\n")
    assert lines[: len(_START)] == _START
    assert lines[-len(_END) - 1 : -1] == _END
    assert lines[-1] == ""  # a final "\n"
    assert len(lines) == len(_START) - 7 + 44 + 4 + 1  # 44 moves
    assert sum(line.startswith("ARC=CW ") for line in lines) == 12
    centres = {
        (words(line)["CENTER:X"], words(line)["CENTER:Y"]) for line in lines if "ARC" in line
    }
    assert centres == {("5.0", "5.0"), ("95.0", "5.0"), ("95.0", "55.0"), ("5.0", "55.0")}
    feeds = [words(line)["F"] for line in lines if "F=" in line]
    assert feeds == ["300.0", "1200.0"] * 3
    assert program.text.isascii()
    assert "\r" not in program.text


@pytest.mark.req("REQ-NCX-002", "REQ-NCX-005")
def test_two_operations_of_one_tool_have_one_tool_block(ctx: Context) -> None:
    # B's plunge feed equals the last F written in A: still written, on B's first feed move.
    second = replace(PROFILE, name="B", feed_classes=(("plunge", 1200.0), ("cut", 1200.0)))
    noted = replace(PROFILE, note=("Rohteil 105 x 65", "Spannung oben"))
    lines = written(ctx, noted, second).text.split("\n")
    assert sum(line.startswith("TOOL=") for line in lines) == 1
    assert sum(line == "COOLANT=ON" for line in lines) == 1
    assert lines[4:8] == [
        'SECTION="PROFILE_1"',
        'COMMENT="Rohteil 105 x 65"',
        'COMMENT="Spannung oben"',
        "TOOL=1 OFFSET:LEN=1 RPM=8000.0 SPINDLE=CW",
    ]
    b = lines.index('SECTION="B"')
    assert lines[b + 1] == "RAPID Z=5.0"
    feeds_in_b = [words(line)["F"] for line in lines[b:] if "F=" in line]
    assert feeds_in_b == ["1200.0"]


@pytest.mark.req("REQ-NCX-002", "REQ-NCX-009")
def test_the_sections_hold_their_lines_and_allowance(ctx: Context) -> None:
    program = written(ctx, PROFILE, replace(PROFILE, name="B", tol_mm=0.02))
    lines = program.text.split("\n")
    first, second = program.sections
    assert first.operation == "operation 1 (PROFILE_1)"
    assert second.operation == "operation 2 (B)"
    assert lines[first.first_line - 1] == 'SECTION="PROFILE_1"'
    assert lines[second.first_line - 1] == 'SECTION="B"'
    assert first.last_line == second.first_line - 1
    assert lines[second.last_line - 1] == "RAPID X=50.0 Y=-15.0 Z=5.0"
    assert lines[second.last_line] == "COOLANT=OFF"
    reserve = ToleranceSet.for_operation(0.01).value
    assert reserve is not None
    assert first.round_limit_mm == reserve.stage_tol_mm("reserve")
    assert first.round_limit_mm == pytest.approx(0.001)
    assert second.round_limit_mm == pytest.approx(0.002)
    assert "ROUND_LIMIT" not in program.text


@pytest.mark.req("REQ-NCX-004")
def test_rapids_have_no_feed_and_the_first_is_z_alone(ctx: Context) -> None:
    lines = written(ctx).text.split("\n")
    rapids = [line for line in lines if line.startswith("RAPID")]
    assert rapids[0] == "RAPID Z=5.0"
    assert len(rapids) == 1 + 1 + 3 * 2
    assert all("F=" not in line for line in rapids)
    assert all(set(words(line)) == {"RAPID", "X", "Y", "Z"} for line in rapids[1:])


@pytest.mark.req("REQ-NCX-005", "REQ-NCX-006")
@pytest.mark.parametrize(("sweep", "word"), [(math.tau, "ARC=CCW"), (-math.tau, "ARC=CW")])
def test_a_full_circle_ends_at_its_start(ctx: Context, sweep: float, word: str) -> None:
    lines = written(ctx, moves=full_circle(sweep)).text.split("\n")
    arc = next(i for i, line in enumerate(lines) if line.startswith("ARC"))
    assert lines[arc] == f"{word} X=10.0 Y=0.0 Z=-1.0 CENTER:X=0.0 CENTER:Y=0.0 F=1200.0"
    assert lines[arc - 1] == "LINE X=10.0 Y=0.0 Z=-1.0 F=300.0"


@pytest.mark.req("REQ-NCX-007")
@pytest.mark.parametrize("offset", [1.0, 40.0])
def test_the_axial_offset_raises_every_z(ctx: Context, offset: float) -> None:
    # write_ncx refuses a ≠ 0 in the slice (REQ-NCX-013, AQ-035); the shift is checked on the
    # move blocks, where it stays for when a setup sheet or NCX's point words exist.
    def blocks(axial_offset_mm: float) -> list[str]:
        (operation,) = record(ctx, replace(PROFILE, axial_offset_mm=axial_offset_mm)).operations
        return move_blocks(operation, printed(operation))

    flat, raised = blocks(0.0), blocks(offset)
    assert len(flat) == len(raised)
    moved = 0
    for before, after in zip(flat, raised, strict=True):
        old, new = words(before), words(after)
        if "Z" in old:
            assert float(new.pop("Z")) == pytest.approx(float(old.pop("Z")) + offset, abs=1e-6)
            moved += 1
        assert new == old  # X, Y, the centre and every other word unchanged
    assert moved == 44


@pytest.mark.req("REQ-NCX-012")
def test_the_text_is_the_same_twice_and_takes_no_machine(ctx: Context) -> None:
    assert written(ctx).text == written(ctx).text
    assert list(inspect.signature(write_ncx).parameters) == ["cl", "program", "ctx"]


@pytest.mark.req("REQ-NCX-001")
def test_the_work_offset_is_the_origin(ctx: Context) -> None:
    result = write_ncx(record(ctx, work_offset=5), RECT_FILLETS, ctx)
    assert result.value is not None
    assert result.value.text.split("\n")[3] == "ORIGIN=5"


@pytest.mark.req("REQ-NCX-001")
def test_a_record_built_directly_is_checked(ctx: Context) -> None:
    data = record(ctx)
    broken = replace(data, work_offset=0)
    with pytest.raises(ValueError, match="REQ-CL-018"):
        write_ncx(broken, RECT_FILLETS, ctx)
