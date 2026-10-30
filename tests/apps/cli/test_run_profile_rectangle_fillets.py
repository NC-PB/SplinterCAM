# SPDX-License-Identifier: Apache-2.0
"""End to end: the golden case `testdata/zoo/profile-rectangle-fillets` through the command line
with the pinned `ncx` (src/splintercam/apps/cli/SPEC.md, REQ-CLI-008; docs/dev/06; DEC-JOB-004).
Skipped with a message naming what is missing when `ncx` is not on the path or
`SPLINTERCAM_NCXCHANGE` is not set; CI builds both (plan 0007, question 3)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from job_files import CASE, MACHINE, listing

_CHECKOUT = os.environ.get("SPLINTERCAM_NCXCHANGE")
_NEEDS = (("ncx on the PATH", shutil.which("ncx")), ("SPLINTERCAM_NCXCHANGE", _CHECKOUT))
_MISSING = [what for what, found in _NEEDS if found is None]


@pytest.mark.req("REQ-CLI-008")
@pytest.mark.skipif(bool(_MISSING), reason=f"end-to-end test needs {' and '.join(_MISSING)}")
def test_the_golden_case_runs_clean_through_the_cli(tmp_path: Path) -> None:
    assert _CHECKOUT is not None
    out = tmp_path / "out"
    out.mkdir()
    machine = Path(_CHECKOUT) / "machines" / MACHINE
    argv = [sys.executable, "-m", "splintercam.apps.cli", "run", str(CASE / "job.json"),
            "--output", str(out), "--machine", str(machine), "--strict"]  # fmt: skip
    run = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=300)
    assert run.returncode == 0, run.stderr
    assert listing(out) == ["RECT_FILLETS.h", "RECT_FILLETS.ncx"]
    severities = [line.split()[0] for line in run.stderr.splitlines()]
    assert set(severities) <= {"INFO"}, run.stderr
    assert run.stdout.splitlines() == [str(out / "RECT_FILLETS.ncx"), str(out / "RECT_FILLETS.h")]
