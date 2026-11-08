# SPDX-License-Identifier: Apache-2.0
"""The written NCX through the real pinned `ncx` on the three shipped mill files (REQ-NCX-001,
011; research 26, test 7; research 27, test 3 in the slice's form). Skipped with a message
without `ncx` on the path or without `SPLINTERCAM_NCXCHANGE` (plan 0007, question 3)."""

import os
import re
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from ncx_programs import PROFILE, RECT_FILLETS, written
from splintercam.cl import ClHeader
from splintercam.foundation import Context, Result, Severity
from splintercam.ncx import NcxCall, NcxProgram, NcxStep, run_ncx

_NCX = shutil.which("ncx")
_CHECKOUT = os.environ.get("SPLINTERCAM_NCXCHANGE")

_MISSING = _NCX is None or _CHECKOUT is None
# AQ-052: where SPLINTERCAM_REQUIRE_NCX is set (the CI runner that builds ncx), the tests must
# not pass by skipping (cnc review, 2026-11-08).
_REQUIRED = bool(os.environ.get("SPLINTERCAM_REQUIRE_NCX"))

_skip_without_ncx = pytest.mark.skipif(
    _MISSING,
    reason="the pinned ncx is not on the path or SPLINTERCAM_NCXCHANGE is not set "
    "(plan 0007, question 3): the written NCX is not checked against NCXchange here",
)
pytestmark = [] if _REQUIRED else [_skip_without_ncx]


@pytest.mark.req("REQ-NCX-011")
def test_the_pinned_ncx_is_there_when_required() -> None:
    assert not (_REQUIRED and _MISSING), "SPLINTERCAM_REQUIRE_NCX is set, but ncx is missing"


_TWO = (PROFILE, replace(PROFILE, name="PROFILE_2", note=("Rohteil 105 x 65",)))
_POINT_2 = replace(PROFILE, point_number=2, axial_offset_mm=2.0)
_MACHINES = ["heidenhain-itnc530", "fanuc-mill-30i", "siemens-840dsl-mill"]


def _run(
    ctx: Context, tmp_path: Path, machine: str, program: NcxProgram
) -> tuple[Result[tuple[NcxStep, ...]], Path]:
    assert _NCX is not None
    assert _CHECKOUT is not None
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir(parents=True)
    out.mkdir()
    ncx_file = work / f"{RECT_FILLETS.name}.ncx"
    ncx_file.write_bytes(program.text.encode("ascii"))
    machine_file = Path(_CHECKOUT) / "machines" / f"{machine}.toml"
    call = NcxCall(Path(_NCX).resolve(), work, ncx_file, machine_file, out)
    return run_ncx(call, program, ctx), out


def _told(result: Result[tuple[NcxStep, ...]], program: NcxProgram) -> str:
    # Every message in full: pytest cuts a long repr, and the line ncx names is at its end.
    told = "\n".join(
        f"{d.code} {d.severity.name} {d.location}: {d.message}" for d in result.diagnostics
    )
    return f"{told}\n--- the program ---\n{program.text}"


def _compiled(out: Path) -> str:
    return "\n".join(path.read_text(errors="replace") for path in sorted(out.iterdir()))


@pytest.mark.req("REQ-NCX-001", "REQ-NCX-011", "REQ-NCX-013", "REQ-NCX-028", "REQ-NCX-029")
@pytest.mark.parametrize("machine", _MACHINES)
@pytest.mark.parametrize(
    "headers", [(PROFILE,), _TWO, (_POINT_2,)], ids=["one", "two", "point-2-at-a-2"]
)
def test_ncx_accepts_the_program(
    ctx: Context, tmp_path: Path, machine: str, headers: tuple[ClHeader, ...]
) -> None:
    program = written(ctx, *headers)
    result, out = _run(ctx, tmp_path, machine, program)
    assert result.ok, _told(result, program)
    assert result.value == (NcxStep.FORMAT, NcxStep.CHECK, NcxStep.COMPILE)
    # At 1e2fd00 rounding to the machine is silent (Z=-3.333333 has more decimals than any
    # shipped mill file, and no CMP020 comes): no message at all.
    assert result.diagnostics == (), _told(result, program)
    assert any(out.iterdir())
    if machine == "heidenhain-itnc530":
        assert (out / "RECT_FILLETS.h").is_file()


@pytest.mark.req("REQ-NCX-021", "REQ-NCX-027")
def test_a_message_of_ncx_names_its_operation(ctx: Context, tmp_path: Path) -> None:
    # The writer refuses a bracket in a note (REQ-NCX-015); in the text it draws NCXchange D390's
    # WARNING on the Fanuc file at the second operation's note line, which maps to that operation.
    program = written(ctx, *_TWO)
    text = program.text.replace('COMMENT="Rohteil 105 x 65"', 'COMMENT="Rohteil (105)"')
    assert text != program.text
    result, _ = _run(ctx, tmp_path, "fanuc-mill-30i", replace(program, text=text))
    assert not result.ok
    warnings = [d for d in result.diagnostics if d.severity is Severity.WARNING]
    assert warnings, _told(result, program)
    assert {d.location for d in warnings} == {"operation 2 (PROFILE_2)"}, _told(result, program)


# Comments as research 27, trap 15 has them: Fanuc `( ... )`, Siemens and Heidenhain `; ...`,
# Heidenhain `* - ...`. What is left of a line is code the control executes.
_COMMENT = re.compile(r"\([^)]*\)|;.*$|\*\s*-.*$")


def _code(out: Path) -> list[str]:
    lines = _compiled(out).split("\n")
    return [stripped for line in lines if (stripped := _COMMENT.sub("", line).strip())]


def _compile(ctx: Context, tmp_path: Path, machine: str, header: ClHeader) -> list[str]:
    program = written(ctx, header)
    result, out = _run(ctx, tmp_path, machine, program)
    assert result.ok, _told(result, program)
    return _code(out)


# D-155: the machine file maps tool and point to the control's register. Point 1 of T1 is the
# tool's own: Fanuc G43 with H1 in one block (R1-13, NCXchange D389: no length offset without
# it), Siemens cutting edge D1, Heidenhain TOOL CALL 1 without an index. Point 2 must not use
# point 1's register; Siemens takes edge D2 (D-155).
_REGISTER_1 = {
    "fanuc-mill-30i": r"\bG43\b.*\bH1\b|\bH1\b.*\bG43\b",
    "siemens-840dsl-mill": r"\bD1\b",
    "heidenhain-itnc530": r"\bTOOL CALL 1(?![.\d])",
}
_REGISTER_2 = {
    "fanuc-mill-30i": r"\bG43\b.*\bH\d+\b|\bH\d+\b.*\bG43\b",
    "siemens-840dsl-mill": r"\bD2\b",
    "heidenhain-itnc530": r"\bTOOL CALL\b",
}


def _found(pattern: str, code: list[str]) -> bool:
    return any(re.search(pattern, line) for line in code)


@pytest.mark.req("REQ-NCX-002", "REQ-NCX-013")
@pytest.mark.parametrize("machine", _MACHINES)
def test_the_compiled_program_applies_the_points_register(
    ctx: Context, tmp_path: Path, machine: str
) -> None:
    first = _compile(ctx, tmp_path / "1", machine, PROFILE)
    assert _found(_REGISTER_1[machine], first), "\n".join(first)
    second = _compile(ctx, tmp_path / "2", machine, replace(PROFILE, point_number=2))
    assert _found(_REGISTER_2[machine], second), "\n".join(second)
    assert not _found(_REGISTER_1[machine], second), "\n".join(second)


_Z = re.compile(r"(?<![A-Z_])Z=?([+-]?(?:\d+\.?\d*|\.\d+))")


@pytest.mark.req("REQ-NCX-007", "REQ-NCX-013")
@pytest.mark.parametrize("machine", _MACHINES)
def test_the_axial_offset_is_applied_once(ctx: Context, tmp_path: Path, machine: str) -> None:
    # D-154: the writer adds a to every Z and the compilers write nothing for TIP_OFFSET (D-155),
    # so every compiled Z of a = 2 lies exactly 2 above a = 0's, never 0 or 4 (cnc review M1).
    flat = _compile(ctx, tmp_path / "0", machine, PROFILE)
    raised = _compile(ctx, tmp_path / "2", machine, replace(PROFILE, axial_offset_mm=2.0))
    assert len(raised) == len(flat), "\n".join(raised)
    shifted = 0
    for before, after in zip(flat, raised, strict=True):
        assert _Z.sub("Z#", after) == _Z.sub("Z#", before), (before, after)
        for old, new in zip(_Z.findall(before), _Z.findall(after), strict=True):
            if old != new:
                assert float(new) - float(old) == pytest.approx(2.0, abs=1e-9), (before, after)
                shifted += 1
    assert shifted >= 10, "\n".join(raised)
