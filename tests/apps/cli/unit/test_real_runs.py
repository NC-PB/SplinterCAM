# SPDX-License-Identifier: Apache-2.0
"""The real `run_job` behind the cli, without `ncx`: the same report twice and the example parts'
exit codes (src/splintercam/apps/cli/SPEC.md, REQ-CLI-007, Example parts; REQ-CLI-005)."""

import json
import os
from pathlib import Path

import pytest

from job_files import CASE, MACHINE, FakeRunNcx, listing
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
        (tmp_path / name).mkdir()  # two empty folders, as REQ-CLI-007 says
        code, out, err = _run(["run", _JOB, "--output", str(tmp_path / name), *options], capsys)
        assert code == 1
        folder = str(tmp_path / name)  # also as JSON and the text report escape it (Windows)
        masked = (out + err).replace(json.dumps(folder)[1:-1], "<output>")
        reports.append(masked.replace(folder, "<output>"))
        assert listing(tmp_path / name) == ["RECT_FILLETS.ncx"]
    assert reports[0] == reports[1]
    codes = ["JOB_INPUTS", "DXF_PART_SIZE", "JOB_NCX_NOT_FOUND"]
    if as_json:
        parsed = json.loads(reports[0])
        assert [d["code"] for d in parsed["diagnostics"]] == codes
        assert parsed["files_left"] == ["<output>" + os.sep + "RECT_FILLETS.ncx"]
    else:
        found = [line.split()[1].rstrip(":") for line in reports[0].splitlines()]
        assert found == [*codes, "FILES_LEFT"]  # the NCX file is there (AQ-040 (c))


@pytest.mark.req("REQ-CLI-005")
def test_without_ncx_an_error_and_nothing_on_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    options = ["--machine", _stand_in(tmp_path), "--ncx", str(tmp_path / "no-ncx")]
    code, out, err = _run(["run", _JOB, "--output", str(tmp_path / "out"), *options], capsys)
    assert (code, out) == (1, "")
    *_, error, left = err.splitlines()
    assert error.startswith("ERROR JOB_NCX_NOT_FOUND")
    assert left.endswith(str(tmp_path / "out" / "RECT_FILLETS.ncx"))


@pytest.mark.req("REQ-CLI-001")
@pytest.mark.req("REQ-CLI-003")
def test_a_warning_under_strict_leaves_no_nc_program(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The cnc review's case (AQ-040): another machine file is a warning; with --strict the real
    # run_job withholds the compiled file (b) and the report names the NCX file left (c).
    exe = tmp_path / "ncx"
    exe.write_bytes(b"")
    monkeypatch.setattr("splintercam.job._output.run_ncx", FakeRunNcx(exe=exe))
    other = tmp_path / "other-machine.toml"
    other.write_bytes(b"")
    out = tmp_path / "out"
    options = ["--machine", str(other), "--ncx", str(exe), "--strict"]
    code, stdout, err = _run(["run", _JOB, "--output", str(out), *options], capsys)
    assert (code, stdout) == (1, "")
    assert listing(out) == ["RECT_FILLETS.ncx"]
    *_, withheld, left = err.splitlines()
    assert "JOB_MACHINE_OVERRIDDEN" in err
    assert withheld.startswith("INFO JOB_STRICT_WITHHELD")
    assert left == f"INFO FILES_LEFT: left on disk, not for the machine: {out / 'RECT_FILLETS.ncx'}"


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
