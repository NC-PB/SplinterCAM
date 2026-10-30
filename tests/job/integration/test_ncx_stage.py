# SPDX-License-Identifier: Apache-2.0
"""Stage 9, `ncx` and the compiled files (src/splintercam/job/SPEC.md, REQ-JOB-017 to 019, 021),
with the fake `run_ncx` of tests/support/job_files.py in place of the real call (DEC-JOB-012)."""

import shutil
import tempfile
from pathlib import Path

import pytest

from job_files import MACHINE, FakeRunNcx, codes, listing
from splintercam.foundation import CANCELLED, Context, Diagnostic, Severity
from splintercam.job import JobReport, default_context, run_job


def _run(job_file: Path, out: Path, ctx: Context, exe: Path | None) -> JobReport:
    return run_job(job_file, out, ncx_executable=exe, ctx=ctx)


def _errors(report: JobReport) -> list[str]:
    return [d.code for d in report.diagnostics if d.severity is Severity.ERROR]


# --- REQ-JOB-017: no ncx --------------------------------------------------------------------------


@pytest.mark.req("REQ-JOB-017")
def test_an_executable_given_that_does_not_exist(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx
) -> None:
    report = _run(job_file, tmp_path / "out", ctx, tmp_path / "missing" / "ncx")
    assert codes(report.diagnostics)[-1] == "JOB_NCX_NOT_FOUND"
    assert _errors(report) == ["JOB_NCX_NOT_FOUND"]
    assert str(tmp_path / "missing" / "ncx") in report.diagnostics[-1].message
    assert listing(tmp_path / "out") == ["RECT_FILLETS.ncx"]
    assert report.ncx_file == tmp_path / "out" / "RECT_FILLETS.ncx"
    assert report.nc_files == ()
    assert fake_ncx.calls == []


@pytest.mark.req("REQ-JOB-017")
def test_no_ncx_on_the_path(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "empty").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    report = _run(job_file, tmp_path / "out", ctx, None)
    assert _errors(report) == ["JOB_NCX_NOT_FOUND"]
    assert listing(tmp_path / "out") == ["RECT_FILLETS.ncx"]
    assert fake_ncx.calls == []


# --- REQ-JOB-018: the working and staging folders -------------------------------------------------


@pytest.mark.req("REQ-JOB-018")
def test_ncx_runs_in_a_new_folder_outside_the_output(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
) -> None:
    out = tmp_path / "out"
    report = _run(job_file, out, ctx, fake_ncx.exe)
    assert report.ok
    [call] = fake_ncx.calls
    assert fake_ncx.seen == [([], [])]  # both folders empty when ncx starts
    assert call.work_dir.parent == call.output_dir.parent
    assert call.work_dir != call.output_dir
    temporary = call.work_dir.parent
    assert temporary.parent == Path(tempfile.gettempdir()).absolute()
    assert out not in temporary.parents
    assert temporary not in out.parents
    assert call.executable == fake_ncx.exe
    assert call.ncx_file == out / "RECT_FILLETS.ncx"
    assert call.machine_file == job_file.parent / "heidenhain-itnc530.toml"
    paths = (call.executable, call.work_dir, call.ncx_file, call.machine_file, call.output_dir)
    assert all(path.is_absolute() for path in paths)
    assert not temporary.exists()


@pytest.mark.req("REQ-JOB-009", "REQ-JOB-018")
def test_relative_paths_reach_ncx_absolute(
    job_file: Path, tmp_path: Path, fake_ncx: FakeRunNcx, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / MACHINE).write_bytes(b"")  # the job's name: no override warning (AQ-036)
    monkeypatch.chdir(tmp_path)
    report = run_job(Path("job") / "job.json", Path("out"), ncx_executable=Path("bin") / "ncx",
                     machine_file=Path(MACHINE), ctx=default_context())  # fmt: skip
    assert report.ok, report.diagnostics
    [call] = fake_ncx.calls
    assert call.executable == tmp_path / "bin" / "ncx"
    assert call.ncx_file == tmp_path / "out" / "RECT_FILLETS.ncx"
    assert call.machine_file == tmp_path / MACHINE
    assert call.work_dir.is_absolute()
    assert call.output_dir.is_absolute()
    assert report.nc_files == (tmp_path / "out" / "RECT_FILLETS.h",)
    assert job_file == tmp_path / "job" / "job.json"


@pytest.mark.req("REQ-JOB-018", "REQ-JOB-021")
@pytest.mark.parametrize("outcome", ["failed", "cancelled"])
def test_the_temporary_folder_is_removed_after_an_error_or_a_cancel(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
    outcome: str,
) -> None:
    fake_ncx.ok = outcome != "failed"
    fake_ncx.cancel = outcome == "cancelled"
    report = _run(job_file, tmp_path / "out", ctx, fake_ncx.exe)
    assert not fake_ncx.calls[0].work_dir.parent.exists()
    assert not report.ok


@pytest.mark.req("REQ-JOB-018")
def test_a_folder_that_cannot_be_removed_is_named(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refuse(path: Path) -> None:
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr("splintercam.job._output.shutil.rmtree", refuse)
    report = _run(job_file, tmp_path / "out", ctx, fake_ncx.exe)
    left = report.diagnostics[-1]
    assert (left.code, left.severity) == ("JOB_WORK_DIR_LEFT", Severity.WARNING)
    temporary = fake_ncx.calls[0].work_dir.parent
    monkeypatch.undo()
    try:
        assert left.location == str(temporary)
        assert report.ok  # a warning: the program is good
        assert report.nc_files == (tmp_path / "out" / "RECT_FILLETS.h",)
    finally:
        shutil.rmtree(temporary)


# --- REQ-JOB-019: the compiled files reach the output only after a clean run ----------------------


@pytest.mark.req("REQ-JOB-019")
def test_a_clean_run_moves_every_file_sorted(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
) -> None:
    fake_ncx.files = ("b.h", "B.i", "a.h")  # distinct on a file system blind to case
    rounded = Diagnostic("NCX_ROUNDED", Severity.INFO, "3 values", "operation 1 (PROFILE_1)")
    fake_ncx.diagnostics = (rounded,)
    out = tmp_path / "out"
    report = _run(job_file, out, ctx, fake_ncx.exe)
    assert report.ok
    assert report.nc_files == (out / "B.i", out / "a.h", out / "b.h")
    assert listing(out) == ["B.i", "RECT_FILLETS.ncx", "a.h", "b.h"]
    assert codes(report.diagnostics)[-1] == "NCX_ROUNDED"
    assert all(path.read_text(encoding="ascii") == "; fake\n" for path in report.nc_files)
    assert not fake_ncx.calls[0].output_dir.parent.exists()


@pytest.mark.req("REQ-JOB-019", "REQ-JOB-021")
@pytest.mark.parametrize("outcome", ["failed", "cancelled"])
def test_a_file_written_before_a_failure_or_a_cancel_is_not_moved(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
    outcome: str,
) -> None:
    fake_ncx.ok = outcome != "failed"
    fake_ncx.cancel = outcome == "cancelled"
    out = tmp_path / "out"
    report = _run(job_file, out, ctx, fake_ncx.exe)
    assert listing(out) == ["RECT_FILLETS.ncx"]
    assert report.nc_files == ()
    assert report.ncx_file == out / "RECT_FILLETS.ncx"
    last = "NCX_STEP_FAILED" if outcome == "failed" else "CANCELLED"
    assert codes(report.diagnostics)[-1] == last
    assert codes(report.diagnostics).count("CANCELLED") == (outcome == "cancelled")


@pytest.mark.req("REQ-JOB-019")
def test_a_clean_run_with_no_file_is_an_error(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
) -> None:
    fake_ncx.files = ()
    report = _run(job_file, tmp_path / "out", ctx, fake_ncx.exe)
    assert _errors(report) == ["JOB_NO_NC_FILE"]
    assert report.nc_files == ()
    assert not report.ok


@pytest.mark.req("REQ-JOB-019", "REQ-JOB-021")
def test_a_cancel_after_a_clean_ncx_moves_nothing(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clean = FakeRunNcx()

    def then_cancel(*args: object) -> object:
        result = clean(*args)  # type: ignore[arg-type]
        ctx.cancel.cancel()
        return result

    monkeypatch.setattr("splintercam.job._output.run_ncx", then_cancel)
    report = _run(job_file, tmp_path / "out", ctx, fake_ncx.exe)
    assert report.diagnostics[-1] == CANCELLED
    assert listing(tmp_path / "out") == ["RECT_FILLETS.ncx"]
    assert report.nc_files == ()
    assert not clean.calls[0].work_dir.parent.exists()
    del fake_ncx


@pytest.mark.req("REQ-JOB-019")
@pytest.mark.parametrize("fails", ["before", "half-way"])
def test_a_failed_move_leaves_no_nc_file(
    job_file: Path, tmp_path: Path, fake_ncx: FakeRunNcx, monkeypatch: pytest.MonkeyPatch,
    fails: str,
) -> None:  # fmt: skip
    # Across volumes a move is a copy; a full disk half-way through must not leave a cut-off
    # program under its real name (DEC-JOB-013).
    fake_ncx.files = ("a.h", "b.h")
    copied: list[str] = []
    real_copy = shutil.copyfile

    def second_fails(source: Path, target: Path) -> object:
        if copied:
            if fails == "half-way":
                Path(target).write_bytes(Path(source).read_bytes()[:3])
            raise OSError(28, "No space left on device")
        assert Path(target).name == f".{Path(source).name}.partial"  # DEC-JOB-013
        copied.append(Path(source).name)
        return real_copy(source, target)

    monkeypatch.setattr("splintercam.job._output.shutil.copyfile", second_fails)
    report = _run(job_file, tmp_path / "out", default_context(), fake_ncx.exe)
    assert copied == ["a.h"]
    assert _errors(report) == ["JOB_OUTPUT_UNWRITABLE"]
    assert listing(tmp_path / "out") == ["RECT_FILLETS.ncx"]
    assert report.nc_files == ()


@pytest.mark.req("REQ-JOB-019")
@pytest.mark.parametrize("entry", ["sub/", "RECT_FILLETS.ncx"])
def test_a_folder_or_a_file_already_there_is_not_moved(
    job_file: Path, tmp_path: Path, ctx: Context, fake_ncx: FakeRunNcx, entry: str
) -> None:
    fake_ncx.files = ("RECT_FILLETS.h", entry)  # "sub/": a folder in the staging folder
    out = tmp_path / "out"
    report = _run(job_file, out, ctx, fake_ncx.exe)
    assert _errors(report) == ["JOB_OUTPUT_UNWRITABLE"]
    assert listing(out) == ["RECT_FILLETS.ncx"]
    assert (out / "RECT_FILLETS.ncx").read_text(encoding="ascii").startswith("FILE=BEGIN")
    assert report.nc_files == ()


@pytest.mark.req("REQ-JOB-018")
def test_a_temporary_folder_that_cannot_be_made_is_an_error(
    job_file: Path, tmp_path: Path, fake_ncx: FakeRunNcx, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(**_: object) -> str:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr("splintercam.job._output.tempfile.mkdtemp", refuse)
    report = _run(job_file, tmp_path / "out", default_context(), fake_ncx.exe)
    assert _errors(report) == ["JOB_WORK_DIR_UNWRITABLE"]
    assert listing(tmp_path / "out") == ["RECT_FILLETS.ncx"]
    assert report.ncx_file == tmp_path / "out" / "RECT_FILLETS.ncx"
    assert fake_ncx.calls == []


@pytest.mark.req("REQ-JOB-018")
def test_a_temporary_folder_inside_the_output_folder_is_refused(
    job_file: Path, tmp_path: Path, fake_ncx: FakeRunNcx, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    monkeypatch.setattr(tempfile, "tempdir", str(out))  # as TMPDIR set to the output folder
    report = _run(job_file, out, default_context(), fake_ncx.exe)
    assert _errors(report) == ["JOB_WORK_DIR_UNWRITABLE"]
    assert listing(out) == ["RECT_FILLETS.ncx"]
    assert fake_ncx.calls == []


@pytest.mark.req("REQ-JOB-019", "REQ-JOB-021")
def test_a_cancel_during_the_move_leaves_no_nc_file(
    job_file: Path, tmp_path: Path, fake_ncx: FakeRunNcx, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = default_context()
    fake_ncx.files = ("a.h", "b.h")
    real_copy = shutil.copyfile

    def then_cancel(source: Path, target: Path) -> object:
        copied = real_copy(source, target)
        ctx.cancel.cancel()  # as from another thread while a slow stick is written
        return copied

    monkeypatch.setattr("splintercam.job._output.shutil.copyfile", then_cancel)
    report = _run(job_file, tmp_path / "out", ctx, fake_ncx.exe)
    assert report.diagnostics[-1].code == "CANCELLED"
    assert codes(report.diagnostics).count("CANCELLED") == 1
    assert listing(tmp_path / "out") == ["RECT_FILLETS.ncx"]
    assert report.nc_files == ()
    assert not report.ok


@pytest.mark.req("REQ-JOB-018")
def test_a_temporary_folder_reached_through_a_link_into_the_output_is_refused(
    job_file: Path, tmp_path: Path, fake_ncx: FakeRunNcx, monkeypatch: pytest.MonkeyPatch
) -> None:
    out, link = tmp_path / "out", tmp_path / "tmp-link"
    out.mkdir()
    try:
        link.symlink_to(out, target_is_directory=True)
    except OSError as error:  # Windows without the symlink privilege
        pytest.skip(f"no symbolic link here: {error}")
    monkeypatch.setattr(tempfile, "tempdir", str(link))
    report = _run(job_file, out, default_context(), fake_ncx.exe)
    assert _errors(report) == ["JOB_WORK_DIR_UNWRITABLE"]
    assert listing(out) == ["RECT_FILLETS.ncx"]  # no stray folder: checked before mkdtemp
    assert fake_ncx.calls == []
