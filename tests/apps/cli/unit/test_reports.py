# SPDX-License-Identifier: Apache-2.0
"""The text and the JSON report (src/splintercam/apps/cli/SPEC.md, REQ-CLI-003, 004;
DEC-CLI-001)."""

import json
from pathlib import Path

import pytest

from cli_fakes import FakeRunJob, diagnostic, report
from splintercam.apps.cli import main
from splintercam.job import Severity

_RUN = ["run", "job.json", "--output", "out"]
_OPERATION = "operation 1 (PROFILE_1)"


def _golden(out: Path) -> FakeRunJob:
    # The golden case's report as `job` gives it with `ncx` (SPEC, Example parts).
    return FakeRunJob(report(
        diagnostic("JOB_INPUTS", Severity.INFO, message="machine m.toml, ncx /bin/ncx"),
        diagnostic("DXF_PART_SIZE", Severity.INFO, "part.dxf", "100 x 60 mm"),
        diagnostic("NCX_ROUNDED", Severity.INFO, _OPERATION, "F rounded to 1000"),
        ncx_file=out / "RECT_FILLETS.ncx", nc_files=(out / "RECT_FILLETS.h",)))  # fmt: skip


@pytest.fixture
def golden(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeRunJob:
    fake = _golden(tmp_path / "out")
    monkeypatch.setattr("splintercam.apps.cli._cli.run_job", fake)
    return fake


@pytest.mark.req("REQ-CLI-003")
def test_the_golden_case_text_report(
    golden: FakeRunJob, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_RUN) == 0
    out, err = capsys.readouterr()
    assert err.splitlines() == [
        "INFO JOB_INPUTS: machine m.toml, ncx /bin/ncx",
        "INFO DXF_PART_SIZE part.dxf: 100 x 60 mm",
        f"INFO NCX_ROUNDED {_OPERATION}: F rounded to 1000",
    ]
    assert out.splitlines() == [str(tmp_path / "out" / "RECT_FILLETS.ncx"),
                                str(tmp_path / "out" / "RECT_FILLETS.h")]  # fmt: skip


@pytest.mark.req("REQ-CLI-003")
@pytest.mark.req("REQ-CLI-004")
def test_relative_paths_are_printed_absolute(
    fake_run_job: FakeRunJob, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_run_job.report = report(ncx_file=Path("out/A.ncx"), nc_files=(Path("out/A.h"),))
    ncx_file, nc_file = str(Path("out/A.ncx").absolute()), str(Path("out/A.h").absolute())
    assert main(_RUN) == 0
    assert capsys.readouterr().out.splitlines() == [ncx_file, nc_file]
    assert main([*_RUN, "--json"]) == 0
    parsed = json.loads(capsys.readouterr().out)
    assert (parsed["ncx_file"], parsed["nc_files"]) == (ncx_file, [nc_file])


@pytest.mark.req("REQ-CLI-003")
def test_line_breaks_are_escaped_one_diagnostic_per_line(
    fake_run_job: FakeRunJob, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_run_job.report = report(
        diagnostic("NCX_OUTPUT_UNREAD", Severity.WARNING, "ncx\ncheck", "line 1\r\nline 2\n")
    )
    assert main(_RUN) == 0
    expected = "WARNING NCX_OUTPUT_UNREAD ncx\\ncheck: line 1\\r\\nline 2\\n\n"
    assert capsys.readouterr().err == expected


@pytest.mark.req("REQ-CLI-003")
def test_backslashes_and_every_other_line_break_are_escaped(
    fake_run_job: FakeRunJob, capsys: pytest.CaptureFixture[str]
) -> None:
    # DEC-CLI-003: the backslash first, so `C:\new` is not read as a line break; every
    # character `str.splitlines` breaks at, and ESC, which a terminal acts on; tab and text kept.
    message = "C:\\new\\run.ncx\v\f\x1c\x85\u2028\u2029\x1b[31m\tÄ"
    fake_run_job.report = report(diagnostic("NCX_STEP_FAILED", location="a\\b", message=message))
    assert main(_RUN) == 1
    err = capsys.readouterr().err
    assert err == ("ERROR NCX_STEP_FAILED a\\\\b: C:\\\\new\\\\run.ncx\\x0b\\x0c\\x1c\\x85"
                   "\\u2028\\u2029\\x1b[31m\tÄ\n")  # fmt: skip
    assert len(err.splitlines()) == 1


def _left(*paths: Path) -> str:
    return f"INFO FILES_LEFT: left on disk, not for the machine: {', '.join(map(str, paths))}\n"


@pytest.mark.req("REQ-CLI-003")
def test_a_failed_run_prints_nothing_on_stdout_and_names_the_files_left(
    fake_run_job: FakeRunJob, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # The NCX file is written before `ncx` fails (REQ-JOB-001); a script must not take it, and
    # the closing line says it is there (AQ-040 (c)).
    fake_run_job.report = report(
        diagnostic("NCX_STEP_FAILED", location="ncx check", message="exited with 1"),
        ncx_file=tmp_path / "A.ncx")  # fmt: skip
    assert main(_RUN) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "ERROR NCX_STEP_FAILED ncx check: exited with 1\n" + _left(tmp_path / "A.ncx")


@pytest.mark.req("REQ-CLI-003")
def test_a_warned_run_under_strict_prints_nothing_on_stdout_and_names_the_files_left(
    fake_run_job: FakeRunJob, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # A report naming an NC file under --strict (a `job` without AQ-040 (b), or a warning after
    # the move): the file is named as left, never on stdout.
    warning = diagnostic("JOB_MACHINE_OVERRIDDEN", Severity.WARNING, "machine")
    fake_run_job.report = report(warning, ncx_file=tmp_path / "A.ncx", nc_files=(tmp_path / "A.h",))
    assert main([*_RUN, "--strict"]) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == ("WARNING JOB_MACHINE_OVERRIDDEN machine: what happened\n"
                   + _left(tmp_path / "A.ncx", tmp_path / "A.h"))  # fmt: skip


@pytest.mark.req("REQ-CLI-003")
@pytest.mark.req("REQ-CLI-004")
def test_no_files_left_line_without_files_or_for_a_usable_run(
    golden: FakeRunJob, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(_RUN) == 0
    assert "FILES_LEFT" not in capsys.readouterr().err
    assert main([*_RUN, "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["files_left"] == []
    golden.report = report(diagnostic("JOB_FILE_UNREADABLE"))
    assert main(_RUN) == 2
    assert "FILES_LEFT" not in capsys.readouterr().err
    assert main([*_RUN, "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["files_left"] == []


@pytest.mark.req("REQ-CLI-003")
def test_a_path_left_is_escaped_as_a_message(
    fake_run_job: FakeRunJob, capsys: pytest.CaptureFixture[str]
) -> None:
    path = Path("o\nut", "A.ncx")
    fake_run_job.report = report(diagnostic("NCX_STEP_FAILED"), ncx_file=path)
    assert main(_RUN) == 1
    escaped = str(path.absolute()).replace("\\", "\\\\").replace("\n", "\\n")
    assert capsys.readouterr().err.splitlines()[-1].endswith(f": {escaped}")


@pytest.mark.req("REQ-CLI-004")
def test_the_golden_case_json_report(
    golden: FakeRunJob, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([*_RUN, "--json"]) == 0
    out, err = capsys.readouterr()
    assert err == ""
    assert out.endswith("}\n")
    assert out.count("\n") == 1
    parsed = json.loads(out)
    assert list(parsed) == ["diagnostics", "exit_code", "files_left", "nc_files", "ncx_file"]
    assert parsed["exit_code"] == 0
    assert parsed["ncx_file"] == str(tmp_path / "out" / "RECT_FILLETS.ncx")
    assert parsed["nc_files"] == [str(tmp_path / "out" / "RECT_FILLETS.h")]
    assert parsed["diagnostics"][0] == {"code": "JOB_INPUTS", "location": None,
                                        "message": "machine m.toml, ncx /bin/ncx",
                                        "severity": "INFO"}  # fmt: skip
    assert [d["location"] for d in parsed["diagnostics"]] == [None, "part.dxf", _OPERATION]
    assert [list(d) for d in parsed["diagnostics"]] == [
        ["code", "location", "message", "severity"]
    ] * 3


@pytest.mark.req("REQ-CLI-004")
def test_the_json_report_is_ascii_and_keeps_the_text(
    fake_run_job: FakeRunJob, capsys: pytest.CaptureFixture[str]
) -> None:
    message = "Fräser Ø10\nzu groß"
    fake_run_job.report = report(
        diagnostic("TOOL_TOO_LARGE", Severity.WARNING, "Tasche 1", message)
    )
    assert main([*_RUN, "--json"]) == 0
    out = capsys.readouterr().out
    assert out.isascii()
    [found] = json.loads(out)["diagnostics"]
    assert found == {"code": "TOOL_TOO_LARGE", "location": "Tasche 1", "message": message,
                     "severity": "WARNING"}  # fmt: skip


@pytest.mark.req("REQ-CLI-004")
@pytest.mark.parametrize(("error", "code"), [("NCX_STEP_FAILED", 1), ("DXF_UNREADABLE", 2)])
def test_a_failed_json_run_names_its_files_only_as_left(
    error: str, code: int, fake_run_job: FakeRunJob, tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    fake_run_job.report = report(diagnostic(error), ncx_file=tmp_path / "A.ncx",
                                 nc_files=(tmp_path / "A.h",))  # fmt: skip
    assert main([*_RUN, "--json"]) == code
    out, err = capsys.readouterr()
    assert err == ""
    parsed = json.loads(out)
    assert (parsed["ncx_file"], parsed["nc_files"], parsed["exit_code"]) == (None, [], code)
    assert parsed["files_left"] == [str(tmp_path / "A.ncx"), str(tmp_path / "A.h")]
    assert parsed["diagnostics"][0]["severity"] == "ERROR"
