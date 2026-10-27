# SPDX-License-Identifier: Apache-2.0
"""The written NCX through the real pinned `ncx` on the three shipped mill files (REQ-NCX-001,
011; research 26, test 7; research 27, test 3 in the slice's form). Skipped with a message
without `ncx` on the path or without `SPLINTERCAM_NCXCHANGE` (plan 0007, question 3)."""

import os
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from ncx_programs import PROFILE, RECT_FILLETS, written
from splintercam.cl import ClHeader
from splintercam.foundation import Context
from splintercam.ncx import NcxCall, NcxStep, run_ncx

_NCX = shutil.which("ncx")
_CHECKOUT = os.environ.get("SPLINTERCAM_NCXCHANGE")

pytestmark = pytest.mark.skipif(
    _NCX is None or _CHECKOUT is None,
    reason="the pinned ncx is not on the path or SPLINTERCAM_NCXCHANGE is not set "
    "(plan 0007, question 3): the written NCX is not checked against NCXchange here",
)

_TWO = (PROFILE, replace(PROFILE, name="PROFILE_2", note=("Rohteil 105 x 65",)))


@pytest.mark.req("REQ-NCX-001", "REQ-NCX-011")
@pytest.mark.parametrize("machine", ["heidenhain-itnc530", "fanuc-mill-30i", "siemens-840dsl-mill"])
@pytest.mark.parametrize("headers", [(PROFILE,), _TWO], ids=["one", "two"])
def test_ncx_accepts_the_program(
    ctx: Context, tmp_path: Path, machine: str, headers: tuple[ClHeader, ...]
) -> None:
    assert _NCX is not None
    assert _CHECKOUT is not None
    program = written(ctx, *headers)
    work, out = tmp_path / "work", tmp_path / "out"
    work.mkdir()
    out.mkdir()
    ncx_file = work / f"{RECT_FILLETS.name}.ncx"
    ncx_file.write_bytes(program.text.encode("ascii"))
    machine_file = Path(_CHECKOUT) / "machines" / f"{machine}.toml"
    call = NcxCall(Path(_NCX).resolve(), work, ncx_file, machine_file, out)
    result = run_ncx(call, program, ctx)
    assert result.ok, result.diagnostics
    assert result.value == (NcxStep.FORMAT, NcxStep.CHECK, NcxStep.COMPILE)
    assert {d.code for d in result.diagnostics} <= {"NCX_ROUNDED"}
    assert any(out.iterdir())
    if machine == "heidenhain-itnc530":
        assert (out / "RECT_FILLETS.h").is_file()
