# SPDX-License-Identifier: Apache-2.0
"""Stage 1's paths (src/splintercam/job/SPEC.md, REQ-JOB-009): the job folder, the machine file
and its override (Peter, AQ-036 2 (b)), the `ncx` executable and `JOB_INPUTS`."""

import os
from pathlib import Path
from typing import Any

import pytest

from job_files import CASE, MACHINE, FakeRunNcx, Job, codes, example, job_folder, listing
from splintercam.foundation import Context, Diagnostic, Severity
from splintercam.job import JobReport, run_job


def _run(tmp_path: Path, ctx: Context, job: Job | str | bytes, **kwargs: Any) -> JobReport:
    job_file = job_folder(tmp_path / "job", job)
    return run_job(job_file, tmp_path / "out", ncx_executable=tmp_path / "no-ncx", ctx=ctx,
                   **kwargs)  # fmt: skip


def _errors(report: JobReport) -> list[tuple[str, str | None]]:
    return [(d.code, d.location) for d in report.diagnostics if d.severity is Severity.ERROR]


def _only(report: JobReport, code: str) -> Diagnostic:
    found = [d for d in report.diagnostics if d.code == code]
    assert len(found) == 1, report.diagnostics
    return found[0]


# --- REQ-JOB-009: paths, the machine file and JOB_INPUTS ------------------------------------------


@pytest.mark.req("REQ-JOB-009")
def test_paths_are_taken_against_the_job_folder(
    tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_file = job_folder(tmp_path / "jobs" / "a", example())
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    relative = Path(os.path.relpath(job_file, elsewhere))  # ../jobs/a/job.json
    report = run_job(relative, Path("out"), ncx_executable=Path("no-ncx"), ctx=ctx)
    assert _errors(report) == [("JOB_NCX_NOT_FOUND", None)]
    inputs = _only(report, "JOB_INPUTS")
    assert inputs.severity is Severity.INFO
    assert str(job_file.parent / MACHINE) in inputs.message
    assert listing(elsewhere / "out") == ["RECT_FILLETS.ncx"]


@pytest.mark.req("REQ-JOB-009")
def test_a_machine_file_given_is_taken_against_the_current_folder(
    tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = example()
    job["machine"] = "not-here.toml"
    job_file = job_folder(tmp_path / "job", job)
    (tmp_path / "cwd").mkdir()
    (tmp_path / "cwd" / "other.toml").write_bytes(b"")
    monkeypatch.chdir(tmp_path / "cwd")
    report = run_job(job_file, tmp_path / "out", ncx_executable=tmp_path / "no-ncx",
                     machine_file=Path("other.toml"), ctx=ctx)  # fmt: skip
    assert "JOB_MACHINE_NOT_FOUND" not in codes(report.diagnostics)
    assert str(tmp_path / "cwd" / "other.toml") in _only(report, "JOB_INPUTS").message
    assert _only(report, "JOB_MACHINE_OVERRIDDEN").location == "machine"  # AQ-036 2 (b)


@pytest.mark.req("REQ-JOB-009", "REQ-JOB-020")
@pytest.mark.parametrize("given", [None, MACHINE, "m.toml"])
def test_a_missing_machine_file_stops_the_run(
    tmp_path: Path, ctx: Context, given: str | None
) -> None:
    job = example()
    if given is None:
        job["machine"] = "missing.toml"
    machine = None if given is None else tmp_path / "missing" / given
    report = _run(tmp_path, ctx, job, machine_file=machine)
    assert _errors(report) == [("JOB_MACHINE_NOT_FOUND", "machine")]
    missing = machine or tmp_path / "job" / "missing.toml"
    assert str(missing) in report.diagnostics[0].message
    # A file of another name given on the call is also an override (AQ-036 2 (b)).
    overridden = ["JOB_MACHINE_OVERRIDDEN"] if given == "m.toml" else []
    assert codes(report.diagnostics) == ["JOB_MACHINE_NOT_FOUND", *overridden, "JOB_INPUTS"]
    assert not (tmp_path / "out").exists()


@pytest.mark.req("REQ-JOB-009", "REQ-JOB-017")
def test_job_inputs_names_the_executable_or_that_none_was_found(
    tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch, fake_ncx: FakeRunNcx
) -> None:
    ncx_exe = fake_ncx.exe  # the fake run_ncx: no process starts
    job_file = job_folder(tmp_path / "job")
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    none_found = run_job(job_file, tmp_path / "out1", ctx=ctx)
    assert "no ncx" in _only(none_found, "JOB_INPUTS").message
    given = run_job(job_file, tmp_path / "out2", ncx_executable=ncx_exe, ctx=ctx,
                    machine_file=tmp_path / "job" / MACHINE)  # fmt: skip
    assert str(ncx_exe) in _only(given, "JOB_INPUTS").message


@pytest.mark.req("REQ-JOB-009")
def test_the_golden_job_without_a_machine_file_is_refused(tmp_path: Path, ctx: Context) -> None:
    report = run_job(CASE / "job.json", tmp_path / "out", ctx=ctx)
    assert _errors(report) == [("JOB_MACHINE_NOT_FOUND", "machine")]
    assert not (tmp_path / "out").exists()


# --- REQ-JOB-009: a machine file given on the call that the job does not name (AQ-036 2 (b)) -----


def _machine(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"")
    return folder / name


@pytest.mark.req("REQ-JOB-009", "REQ-JOB-020")
def test_a_machine_file_of_another_name_is_a_warning(
    tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    other = _machine(tmp_path / "machines", "fanuc-mill-30i.toml")
    job_file = job_folder(tmp_path / "job")
    report = run_job(job_file, tmp_path / "out", ncx_executable=fake_ncx.exe,
                     machine_file=other, ctx=ctx)  # fmt: skip
    overridden = _only(report, "JOB_MACHINE_OVERRIDDEN")
    assert (overridden.severity, overridden.location) == (Severity.WARNING, "machine")
    assert "fanuc-mill-30i.toml" in overridden.message
    assert MACHINE in overridden.message
    assert codes(report.diagnostics) == ["JOB_MACHINE_OVERRIDDEN", "JOB_INPUTS", "DXF_PART_SIZE"]
    assert fake_ncx.calls[0].machine_file == other  # the given file is used (DEC-JOB-004)
    assert report.ok  # a warning: the program is still compiled (AQ-036 1 (a))


@pytest.mark.req("REQ-JOB-009")
def test_a_machine_file_of_the_jobs_name_elsewhere_is_no_warning(
    tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    same = _machine(tmp_path / "checkout" / "machines", MACHINE)
    report = run_job(job_folder(tmp_path / "job"), tmp_path / "out", ncx_executable=fake_ncx.exe,
                     machine_file=same, ctx=ctx)  # fmt: skip
    assert codes(report.diagnostics) == ["JOB_INPUTS", "DXF_PART_SIZE"]
    assert fake_ncx.calls[0].machine_file == same


@pytest.mark.req("REQ-JOB-009")
@pytest.mark.parametrize(
    ("in_job", "given", "warned"),
    [
        (f"machines/{MACHINE}", MACHINE, False),  # the folder in the job is not compared
        (MACHINE, MACHINE.upper(), True),  # names compared case included (DEC-JOB-015)
        ("", MACHINE, False),  # JOB_VALUE_INVALID already
        (5, MACHINE, False),
    ],
)
def test_the_override_compares_file_names_only(
    tmp_path: Path, ctx: Context, in_job: object, given: str, warned: bool
) -> None:
    job = example()
    job["machine"] = in_job
    report = _run(tmp_path, ctx, job, machine_file=_machine(tmp_path / "given", given))
    assert ("JOB_MACHINE_OVERRIDDEN" in codes(report.diagnostics)) == warned


@pytest.mark.req("REQ-JOB-009", "REQ-JOB-020")
def test_the_override_warning_comes_after_stage_1s_errors(tmp_path: Path, ctx: Context) -> None:
    job = example()
    job["part"]["dxf"] = ""
    job["extra"] = 1
    other = _machine(tmp_path / "machines", "other.toml")
    report = _run(tmp_path, ctx, job, machine_file=other)
    assert codes(report.diagnostics) == [
        "JOB_VALUE_INVALID",
        "JOB_KEY_UNKNOWN",
        "JOB_MACHINE_OVERRIDDEN",
        "JOB_INPUTS",
    ]
