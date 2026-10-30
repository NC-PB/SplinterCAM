# SPDX-License-Identifier: Apache-2.0
"""End to end: the golden case `testdata/zoo/profile-rectangle-fillets` through the command line
with the pinned `ncx` (src/splintercam/apps/cli/SPEC.md, REQ-CLI-008, Example parts; docs/dev/06;
DEC-JOB-004). Skipped with a message naming what is missing when `ncx` is not on the path or
`SPLINTERCAM_NCXCHANGE` is not set; CI has both (plan 0007, question 3)."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from job_files import CASE, listing

_CASE: dict[str, Any] = json.loads((CASE / "case.json").read_text(encoding="utf-8"))
_NCX: dict[str, Any] = _CASE["checks"]["ncx"]
_CHECKOUT = os.environ.get("SPLINTERCAM_NCXCHANGE")
_NEEDS = (("ncx on the PATH", shutil.which("ncx")), ("SPLINTERCAM_NCXCHANGE", _CHECKOUT))
_MISSING = [what for what, found in _NEEDS if found is None]


@pytest.mark.req("REQ-CLI-008")
@pytest.mark.skipif(bool(_MISSING), reason=f"end-to-end test needs {' and '.join(_MISSING)}")
@pytest.mark.parametrize("strict", [True, False])
def test_the_golden_case_runs_clean_through_the_cli(strict: bool, tmp_path: Path) -> None:
    assert _CHECKOUT is not None
    out = tmp_path / "out"
    out.mkdir()
    machine = Path(_CHECKOUT) / "machines" / _NCX["machine"]
    argv = [sys.executable, "-m", "splintercam.apps.cli", "run", str(CASE / "job.json"),
            "--output", str(out), "--machine", str(machine)]  # fmt: skip
    run = subprocess.run([*argv, *(["--strict"] if strict else [])], capture_output=True,
                         text=True, check=False, timeout=300)  # fmt: skip
    assert run.returncode == 0, run.stderr
    assert listing(out) == sorted(_NCX["files"])
    lines = run.stderr.splitlines()
    found = [[*line.split(" ", 2), "", ""][:2] for line in lines]  # no IndexError on ""
    assert [(s, code.rstrip(":")) for s, code in found] == [("INFO", c) for c in _NCX["codes"]], (
        run.stderr)  # fmt: skip
    assert lines[-1].startswith("INFO NCX_ROUNDED operation 1 (PROFILE_1): ")
    assert run.stdout.splitlines() == [str(out / "RECT_FILLETS.ncx"), str(out / "RECT_FILLETS.h")]
