# SPDX-License-Identifier: Apache-2.0
"""`run_job(strict=True)`: a WARNING withholds the compiled files as an ERROR does, the NCX file
still written (src/splintercam/job/SPEC.md, REQ-JOB-001, 019; Peter, AQ-040 (b); DEC-JOB-016),
with the fake `run_ncx` of tests/support/job_files.py (DEC-JOB-012)."""

import shutil
from pathlib import Path
from typing import Any

import pytest

from job_files import FakeRunNcx, codes, listing
from splintercam.foundation import Context, Diagnostic, Severity
from splintercam.job import JobReport, run_job

_WARNED = Diagnostic("NCX_OUTPUT_UNREAD", Severity.WARNING, "a line ncx printed", "ncx check")
_ROUNDED = Diagnostic("NCX_ROUNDED", Severity.INFO, "3 values", "operation 1 (PROFILE_1)")


def _run(job_file: Path, out: Path, ctx: Context, fake: FakeRunNcx, *, strict: bool) -> JobReport:
    return run_job(job_file, out, ncx_executable=fake.exe, ctx=ctx, strict=strict)


@pytest.mark.req("REQ-JOB-019")
def test_a_warning_from_ncx_withholds_the_compiled_files(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    fake_ncx.diagnostics = (_WARNED,)
    out = tmp_path / "out"
    report = _run(job_file, out, ctx, fake_ncx, strict=True)
    assert len(fake_ncx.calls) == 1  # ncx still checks the program, its verdict is reported
    assert listing(out) == ["RECT_FILLETS.ncx"]
    assert (report.ncx_file, report.nc_files) == (out / "RECT_FILLETS.ncx", ())
    assert codes(report.diagnostics)[-2:] == ["NCX_OUTPUT_UNREAD", "JOB_STRICT_WITHHELD"]
    withheld = report.diagnostics[-1]
    assert withheld.severity is Severity.INFO
    assert withheld.location == str(out)
    assert "1 warning" in withheld.message
    assert not fake_ncx.calls[0].output_dir.parent.exists()  # the staged files are removed


@pytest.mark.req("REQ-JOB-001")
@pytest.mark.req("REQ-JOB-019")
def test_a_warning_of_an_earlier_stage_withholds_them_too(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    other = tmp_path / "other-machine.toml"  # JOB_MACHINE_OVERRIDDEN, stage 1 (DEC-JOB-015)
    other.write_bytes(b"")
    out = tmp_path / "out"
    report = run_job(job_file, out, ncx_executable=fake_ncx.exe, machine_file=other, ctx=ctx,
                     strict=True)  # fmt: skip
    assert "JOB_MACHINE_OVERRIDDEN" in codes(report.diagnostics)
    assert codes(report.diagnostics)[-1] == "JOB_STRICT_WITHHELD"
    assert "1 warning" in report.diagnostics[-1].message  # the override, counted from stage 1
    assert listing(out) == ["RECT_FILLETS.ncx"]
    assert report.nc_files == ()


@pytest.mark.req("REQ-JOB-019")
def test_strict_with_info_only_moves_the_files(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    fake_ncx.diagnostics = (_ROUNDED,)  # INFO never withholds (REQ-CLI-005)
    out = tmp_path / "out"
    report = _run(job_file, out, ctx, fake_ncx, strict=True)
    assert report.nc_files == (out / "RECT_FILLETS.h",)
    assert "JOB_STRICT_WITHHELD" not in codes(report.diagnostics)


@pytest.mark.req("REQ-JOB-019")
def test_without_strict_a_warning_moves_the_files_as_before(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    fake_ncx.diagnostics = (_WARNED,)
    out = tmp_path / "out"
    report = _run(job_file, out, ctx, fake_ncx, strict=False)
    assert report.nc_files == (out / "RECT_FILLETS.h",)
    assert codes(report.diagnostics)[-1] == "NCX_OUTPUT_UNREAD"


@pytest.mark.req("REQ-JOB-018")
@pytest.mark.req("REQ-JOB-019")
def test_a_temporary_folder_left_after_the_move_takes_the_files_back(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    # The one warning after the move (DEC-JOB-016): under strict the moved files go again.
    def refuse(path: Path) -> None:
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr("splintercam.job._output.shutil.rmtree", refuse)
    out = tmp_path / "out"
    report = _run(job_file, out, ctx, fake_ncx, strict=True)
    temporary = fake_ncx.calls[0].work_dir.parent
    monkeypatch.undo()
    try:
        assert codes(report.diagnostics)[-2:] == ["JOB_WORK_DIR_LEFT", "JOB_STRICT_WITHHELD"]
        assert "1 warning" in report.diagnostics[-1].message
        assert "may hold NC files" in report.diagnostics[-2].message  # what may be in there
        assert listing(out) == ["RECT_FILLETS.ncx"]
        assert report.nc_files == ()
    finally:
        shutil.rmtree(temporary)


@pytest.mark.req("REQ-JOB-019")
def test_strict_with_no_staged_file_is_still_an_error(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    fake_ncx.files = ()
    fake_ncx.diagnostics = (_WARNED,)
    report = _run(job_file, tmp_path / "out", ctx, fake_ncx, strict=True)
    assert codes(report.diagnostics)[-1] == "JOB_NO_NC_FILE"  # ncx wrote nothing: an error
    assert not report.ok


@pytest.mark.req("REQ-JOB-019")
@pytest.mark.req("REQ-JOB-021")
def test_a_late_cancel_under_strict_is_a_cancel(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    fake_ncx.diagnostics = (_WARNED,)

    def clean_then_cancel(*args: Any) -> Any:
        result = FakeRunNcx.__call__(fake_ncx, *args)
        ctx.cancel.cancel()
        return result

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("splintercam.job._output.run_ncx", clean_then_cancel)
        report = _run(job_file, tmp_path / "out", ctx, fake_ncx, strict=True)
    assert codes(report.diagnostics)[-1] == "CANCELLED"
    assert "JOB_STRICT_WITHHELD" not in codes(report.diagnostics)
    assert report.nc_files == ()


@pytest.mark.req("REQ-JOB-019")
def test_strict_after_an_ncx_failure_adds_nothing(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    fake_ncx.ok = False
    fake_ncx.diagnostics = (_WARNED,)
    report = _run(job_file, tmp_path / "out", ctx, fake_ncx, strict=True)
    assert codes(report.diagnostics)[-1] == "NCX_STEP_FAILED"  # the error says it already
    assert "JOB_STRICT_WITHHELD" not in codes(report.diagnostics)
