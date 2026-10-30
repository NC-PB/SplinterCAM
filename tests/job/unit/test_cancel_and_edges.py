# SPDX-License-Identifier: Apache-2.0
"""Cancelling, determinism, the default context and a strategy that gives nothing
(src/splintercam/job/SPEC.md, REQ-JOB-001, 014, 016, 021, 022)."""

from pathlib import Path

import pytest

from job_files import FakeRunNcx, codes, example, job_folder, listing, operation
from splintercam.cl import ClOperation
from splintercam.foundation import (
    CANCELLED,
    TOLERANCE_DEFAULTS,
    Context,
    Diagnostic,
    Result,
    Severity,
    ToleranceSet,
)
from splintercam.job import JobReport, default_context, run_job
from splintercam.job._registry import Strategy, profile_input
from splintercam.strategies.profile import DECLARATIONS, STRATEGY_ID, ProfileInput, plan_profile


def _run(job_file: Path, out: Path, ctx: Context, exe: Path | None = None) -> JobReport:
    missing = out.parent / "no-ncx"
    return run_job(job_file, out, ncx_executable=exe or missing, ctx=ctx)


def _errors(report: JobReport) -> list[str]:
    return [d.code for d in report.diagnostics if d.severity is Severity.ERROR]


def _fake_registry(monkeypatch: pytest.MonkeyPatch, plan: object) -> None:
    fake = Strategy(DECLARATIONS, profile_input, plan)  # type: ignore[arg-type]
    monkeypatch.setattr("splintercam.job._run.REGISTRY", {STRATEGY_ID: fake})


# --- REQ-JOB-021: cancelling ----------------------------------------------------------------------


@pytest.mark.req("REQ-JOB-021")
def test_a_cancel_set_by_a_strategy_stops_before_the_next_operation(
    tmp_path: Path,
    ctx: Context,
    monkeypatch: pytest.MonkeyPatch,
    fake_ncx: FakeRunNcx,
) -> None:
    job = example()
    job["operations"].append(dict(operation(job), name="PROFILE_2"))
    names: list[str] = []

    def plan(task: ProfileInput, op_ctx: Context) -> Result[ClOperation]:
        names.append(task.operation.name)
        planned = plan_profile(task, op_ctx)
        op_ctx.cancel.cancel()
        return planned

    _fake_registry(monkeypatch, plan)
    report = _run(job_folder(tmp_path / "job", job), tmp_path / "out", ctx, fake_ncx.exe)
    assert names == ["PROFILE_1"]
    assert report.diagnostics[-1] == CANCELLED
    assert codes(report.diagnostics).count("CANCELLED") == 1
    assert (report.cl_data, report.ncx_file, report.nc_files) == (None, None, ())
    assert listing(tmp_path / "out") == []
    assert fake_ncx.calls == []
    assert not report.ok


@pytest.mark.req("REQ-JOB-021")
def test_a_cancel_before_the_run_reads_nothing(
    job_file: Path, tmp_path: Path, ctx: Context
) -> None:
    ctx.cancel.cancel()
    report = _run(job_file, tmp_path / "out", ctx)
    assert report.diagnostics == (CANCELLED,)
    assert not (tmp_path / "out").exists()


@pytest.mark.req("REQ-JOB-021")
def test_a_cancel_inside_a_module_is_reported_once(
    tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch, job_file: Path
) -> None:
    def plan(task: ProfileInput, op_ctx: Context) -> Result[ClOperation]:
        del task
        op_ctx.cancel.cancel()
        return Result(None, (CANCELLED,))

    _fake_registry(monkeypatch, plan)
    report = _run(job_file, tmp_path / "out", ctx)
    assert codes(report.diagnostics).count("CANCELLED") == 1
    assert report.diagnostics[-1].location == "operation 1 (PROFILE_1)"


# --- REQ-JOB-022 and the default context ----------------------------------------------------------


@pytest.mark.req("REQ-JOB-022")
def test_two_runs_write_the_same_bytes(job_file: Path, tmp_path: Path) -> None:
    first = _run(job_file, tmp_path / "one", default_context())
    second = _run(job_file, tmp_path / "two", default_context())
    assert first.ncx_file is not None
    assert second.ncx_file is not None
    assert first.ncx_file.read_bytes() == second.ncx_file.read_bytes()


@pytest.mark.req("REQ-JOB-001")
def test_the_default_context(job_file: Path, tmp_path: Path) -> None:
    ctx = default_context()
    default_tol = TOLERANCE_DEFAULTS["chord_tol_finishing_mm"].default
    assert ctx.tolerances == ToleranceSet.for_operation(default_tol).value
    assert not ctx.cancel.is_cancelled
    assert default_context().cancel is not ctx.cancel
    assert ctx.logger.name == "splintercam.job"
    assert ctx.seed == 0
    ctx.progress(0.5)
    report = run_job(job_file, tmp_path / "out", ncx_executable=tmp_path / "no-ncx")
    assert _errors(report) == ["JOB_NCX_NOT_FOUND"]


@pytest.mark.req("REQ-JOB-014")
def test_a_strategy_with_no_value_and_no_error_is_a_programming_error(
    job_file: Path, tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    def plan(task: ProfileInput, op_ctx: Context) -> Result[ClOperation]:
        del task, op_ctx
        return Result(None, ())  # would leave the operation out of the program (DEC-JOB-002)

    _fake_registry(monkeypatch, plan)
    with pytest.raises(ValueError, match="no value and no error"):
        _run(job_file, tmp_path / "out", ctx)
    assert listing(tmp_path / "out") == []


@pytest.mark.req("REQ-JOB-016", "REQ-JOB-021")
def test_a_cancel_while_the_ncx_file_is_written_still_names_it(
    job_file: Path, tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Path.write_bytes

    def then_cancel(self: Path, data: bytes) -> int:
        written = real(self, data)
        ctx.cancel.cancel()
        return written

    monkeypatch.setattr(Path, "write_bytes", then_cancel)
    report = _run(job_file, tmp_path / "out", ctx)
    assert report.diagnostics[-1] == CANCELLED
    assert report.ncx_file == tmp_path / "out" / "RECT_FILLETS.ncx"
    assert listing(tmp_path / "out") == ["RECT_FILLETS.ncx"]
    assert report.nc_files == ()


@pytest.mark.req("REQ-JOB-014")
def test_a_strategy_with_no_value_is_an_error_after_another_operations_failure(
    tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = example()
    job["operations"].append(dict(operation(job), name="PROFILE_2"))

    def plan(task: ProfileInput, op_ctx: Context) -> Result[ClOperation]:
        del op_ctx
        if task.operation.name == "PROFILE_1":
            return Result(None, (Diagnostic("FAKE", Severity.ERROR, "fails", None),))
        return Result(None, ())

    _fake_registry(monkeypatch, plan)
    with pytest.raises(ValueError, match="no value and no error"):
        _run(job_folder(tmp_path / "job", job), tmp_path / "out", ctx)


@pytest.mark.req("REQ-JOB-001")
def test_a_stage_with_no_value_and_only_a_warning_is_a_programming_error(
    job_file: Path, tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    warning = Diagnostic("FAKE_WARNING", Severity.WARNING, "no value", None)

    def no_value(*_: object) -> Result[object]:
        return Result(None, (warning,))

    monkeypatch.setattr("splintercam.job._run.read_dxf_contour", no_value)
    with pytest.raises(ValueError, match="no value and no error"):
        _run(job_file, tmp_path / "out", ctx)


@pytest.mark.req("REQ-JOB-016")
def test_a_partial_file_that_cannot_be_removed_is_named(
    job_file: Path, tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: Path, data: bytes) -> int:
        del self, data
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "write_bytes", broken)

    def kept(path: Path) -> bool:
        del path
        return False

    monkeypatch.setattr("splintercam.job._output._removed", kept)
    report = _run(job_file, tmp_path / "out", ctx)
    message = report.diagnostics[-1].message
    assert report.diagnostics[-1].code == "JOB_OUTPUT_UNWRITABLE"
    assert "No space left" in message  # the first reason kept
    assert ".RECT_FILLETS.ncx.partial left there" in message
