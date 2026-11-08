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
from splintercam.foundation import Context, Result
from splintercam.ncx import NcxCall, NcxProgram, NcxStep, run_ncx

_NCX = shutil.which("ncx")
_CHECKOUT = os.environ.get("SPLINTERCAM_NCXCHANGE")

pytestmark = pytest.mark.skipif(
    _NCX is None or _CHECKOUT is None,
    reason="the pinned ncx is not on the path or SPLINTERCAM_NCXCHANGE is not set "
    "(plan 0007, question 3): the written NCX is not checked against NCXchange here",
)

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


@pytest.mark.req("REQ-NCX-001", "REQ-NCX-011", "REQ-NCX-013", "REQ-NCX-021", "REQ-NCX-028")
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
    assert {d.code for d in result.diagnostics} <= {"NCX_ROUNDED"}
    # Z=-3.333333 has more decimals than any shipped mill file: each operation reports its
    # CMP020s at its own location, so the line-to-operation mapping is checked too (REQ-NCX-021).
    locations = {d.location for d in result.diagnostics}
    assert locations == {section.operation for section in program.sections}
    assert any(out.iterdir())
    if machine == "heidenhain-itnc530":
        assert (out / "RECT_FILLETS.h").is_file()


# D-155: the machine file maps tool and point to the control's register; for point 1 of T1, the
# tool's own: Fanuc G43 with H1 (R1-13, NCXchange D389: no length offset without one), Siemens
# cutting edge D1, Heidenhain TOOL CALL 1.
_REGISTER_1 = {
    "fanuc-mill-30i": (r"\bG43\b", r"\bH1\b"),
    "siemens-840dsl-mill": (r"\bD1\b",),
    "heidenhain-itnc530": (r"\bTOOL CALL 1\b",),
}


@pytest.mark.req("REQ-NCX-002", "REQ-NCX-013")
@pytest.mark.parametrize("machine", _MACHINES)
def test_the_compiled_program_applies_the_points_register(
    ctx: Context, tmp_path: Path, machine: str
) -> None:
    first = written(ctx)
    result, out = _run(ctx, tmp_path / "1", machine, first)
    assert result.ok, _told(result, first)
    compiled = _compiled(out)
    for pattern in _REGISTER_1[machine]:
        assert re.search(pattern, compiled), f"{pattern} not in\n{compiled}"
    # Point 2 of the same tool, a = 0: another register, so another compiled program; Siemens
    # takes edge D2 (D-155).
    second = written(ctx, replace(PROFILE, point_number=2))
    result, out = _run(ctx, tmp_path / "2", machine, second)
    assert result.ok, _told(result, second)
    other = _compiled(out)
    assert other != compiled, compiled
    if machine == "siemens-840dsl-mill":
        assert re.search(r"\bD2\b", other), other
