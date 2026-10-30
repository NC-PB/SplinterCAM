# SPDX-License-Identifier: Apache-2.0
"""The real `run_job` behind the cli, without `ncx`: the same report twice and the example parts'
exit codes (src/splintercam/apps/cli/SPEC.md, REQ-CLI-007, Example parts; REQ-CLI-005)."""

import json
from pathlib import Path

import pytest

from job_files import CASE, MACHINE, listing
from splintercam.apps.cli import main

_JOB = str(CASE / "job.json")


def _stand_in(tmp_path: Path) -> str:
    # Any existing file of the job's machine name stands for the machine (no
    # JOB_MACHINE_OVERRIDDEN); a missing --ncx stops the run at JOB_NCX_NOT_FOUND after the
    # record is built (SPEC, REQ-CLI-007).
    machine = tmp_path / MACHINE
    machine.write_bytes(b"")
    return str(machine)


def _run(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = main(argv)
    out, err = capsys.readouterr()
    return code, out, err


@pytest.mark.req("REQ-CLI-007")
@pytest.mark.parametrize("as_json", [False, True])
def test_the_same_job_twice_prints_the_same_report_but_for_the_folders(
    as_json: bool, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    options = ["--machine", _stand_in(tmp_path), "--ncx", str(tmp_path / "no-ncx")]
    options += ["--json"] if as_json else []
    reports: list[str] = []
    for name in ("first", "second"):
        code, out, err = _run(["run", _JOB, "--output", str(tmp_path / name), *options], capsys)
        assert code == 1
        reports.append((out + err).replace(str(tmp_path / name), "<output>"))
        assert listing(tmp_path / name) == ["RECT_FILLETS.ncx"]
    assert reports[0] == reports[1]
    if as_json:
        found = [d["code"] for d in json.loads(reports[0])["diagnostics"]]
    else:
        found = [line.split()[1].rstrip(":") for line in reports[0].splitlines()]
    assert found == ["JOB_INPUTS", "DXF_PART_SIZE", "JOB_NCX_NOT_FOUND"]


@pytest.mark.req("REQ-CLI-005")
def test_without_ncx_an_error_and_nothing_on_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    options = ["--machine", _stand_in(tmp_path), "--ncx", str(tmp_path / "no-ncx")]
    code, out, err = _run(["run", _JOB, "--output", str(tmp_path / "out"), *options], capsys)
    assert (code, out) == (1, "")
    assert err.splitlines()[-1].startswith("ERROR JOB_NCX_NOT_FOUND")


@pytest.mark.req("REQ-CLI-005")
def test_without_machine_the_golden_job_is_code_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The machine file is not in the case folder (DEC-JOB-004).
    code, out, err = _run(["run", _JOB, "--output", str(tmp_path / "out")], capsys)
    assert (code, out) == (2, "")
    assert "ERROR JOB_MACHINE_NOT_FOUND" in err


@pytest.mark.req("REQ-CLI-005")
def test_a_missing_job_file_is_code_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = _run(["run", str(tmp_path / "missing.json"), "--output",
                           str(tmp_path / "out")], capsys)  # fmt: skip
    assert (code, out) == (2, "")
    assert err.startswith("ERROR JOB_FILE_UNREADABLE")
