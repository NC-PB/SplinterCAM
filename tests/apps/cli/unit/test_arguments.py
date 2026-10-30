# SPDX-License-Identifier: Apache-2.0
"""The `run` command's arguments, the one `run_job` call, the imports and argparse's exits
(src/splintercam/apps/cli/SPEC.md, REQ-CLI-001, 002, 006)."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from cli_fakes import FakeRunJob
from splintercam.apps.cli import main

_CLI = Path(__file__).parents[4] / "src" / "splintercam" / "apps" / "cli"


@pytest.mark.req("REQ-CLI-001")
@pytest.mark.req("REQ-CLI-002")
def test_the_options_reach_run_job(fake_run_job: FakeRunJob) -> None:
    code = main(["run", "a/job.json", "--output", "out", "--ncx", "bin/ncx",
                 "--machine", "m.toml", "--strict", "--json"])  # fmt: skip
    assert code == 0
    assert fake_run_job.calls == [{"job_file": Path("a/job.json"), "output_dir": Path("out"),
                                   "ncx_executable": Path("bin/ncx"),
                                   "machine_file": Path("m.toml")}]  # fmt: skip


@pytest.mark.req("REQ-CLI-001")
def test_the_optional_paths_default_to_none(fake_run_job: FakeRunJob) -> None:
    assert main(["run", "job.json", "--output", "out"]) == 0
    [call] = fake_run_job.calls
    assert call["ncx_executable"] is None
    assert call["machine_file"] is None


@pytest.mark.req("REQ-CLI-002")
def test_the_cli_imports_only_job_from_splintercam() -> None:
    imported: set[str] = set()
    for path in sorted(_CLI.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
    assert {name for name in imported if name.startswith("splintercam")} == {"splintercam.job"}


@pytest.mark.req("REQ-CLI-005")
@pytest.mark.req("REQ-CLI-006")
@pytest.mark.parametrize(
    "argv",
    [[], ["run"], ["run", "job.json"], ["run", "--output", "out"], ["make", "job.json"],
     ["run", "job.json", "--output", "out", "--unknown"], ["run", "a", "b", "--output", "out"]],
)  # fmt: skip
def test_a_usage_error_is_code_2_with_the_usage_on_stderr(
    argv: list[str], fake_run_job: FakeRunJob, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith("usage: splintercam")
    assert fake_run_job.calls == []


@pytest.mark.req("REQ-CLI-006")
@pytest.mark.parametrize("argv", [["--help"], ["run", "--help"]])
def test_help_is_code_0_on_stdout(
    argv: list[str], fake_run_job: FakeRunJob, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(argv) == 0
    out, err = capsys.readouterr()
    assert out.startswith("usage: splintercam")
    assert err == ""
    assert fake_run_job.calls == []


@pytest.mark.req("REQ-CLI-001")
@pytest.mark.req("REQ-CLI-006")
def test_run_help_names_every_option(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "--help"]) == 0
    out = capsys.readouterr().out
    for option in ("JOB_FILE", "--output", "--ncx", "--machine", "--strict", "--json"):
        assert option in out
    # The safe default of AQ-040 (a): after a failed run, files may be left in the folder.
    assert "take no file from the output folder" in " ".join(out.split())


@pytest.mark.req("REQ-CLI-006")
@pytest.mark.parametrize(("argv", "code", "on_stdout"), [(["--help"], 0, True),
                                                         (["run"], 2, False)])  # fmt: skip
def test_python_dash_m_runs_main_and_returns_its_code(
    argv: list[str], code: int, on_stdout: bool
) -> None:
    # The console script's target is `__main__.entry` (pyproject.toml); `-m` runs the same.
    run = subprocess.run([sys.executable, "-m", "splintercam.apps.cli", *argv],
                         capture_output=True, text=True, check=False, timeout=60)  # fmt: skip
    assert run.returncode == code
    assert (run.stdout if on_stdout else run.stderr).startswith("usage: splintercam")
    assert (run.stderr if on_stdout else run.stdout) == ""


@pytest.mark.req("REQ-CLI-006")
def test_a_clean_run_prints_nothing_but_its_report(
    fake_run_job: FakeRunJob, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["run", "job.json", "--output", "out"]) == 0
    assert capsys.readouterr() == ("", "")  # an empty report, no files
