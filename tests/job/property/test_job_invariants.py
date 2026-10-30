# SPDX-License-Identifier: Apache-2.0
"""The SPEC's invariants (src/splintercam/job/SPEC.md, Invariants): a fault injected at a
generated stage and a fake `ncx` with generated outcomes; the files present afterwards match the
stage reached, a report with an ERROR or `CANCELLED` has no NC file, and an `ok` one has the NCX
file and at least one NC file. The strategy is a fake that returns the example's planned
operation, computed once, so an example takes milliseconds."""

import functools
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from job_files import FakeRunNcx, example, job_folder, listing, operation
from profile_checks import make_context, task
from splintercam.cl import ClOperation
from splintercam.foundation import Context, Diagnostic, Result, Severity
from splintercam.job import JobReport, run_job
from splintercam.job._registry import Strategy, profile_input
from splintercam.strategies.profile import DECLARATIONS, STRATEGY_ID, ProfileInput, plan_profile

_STAGES = ("none", "file", "output", "model", "dxf", "plan", "ncx_words", "write", "no_ncx")
_OUTCOMES = st.sampled_from(["clean", "failed", "cancelled", "no_file"])


@functools.cache
def _planned() -> ClOperation:
    ctx = make_context()
    planned = plan_profile(task(ctx), ctx).value
    assert planned is not None
    return planned


def _plan(fails: bool):
    def plan(task_: ProfileInput, ctx: Context) -> Result[ClOperation]:
        del task_, ctx
        if fails:
            return Result(None, (Diagnostic("FAKE", Severity.ERROR, "fails", None),))
        return Result(_planned())

    return plan


def _folder(base: Path, stage: str) -> tuple[Path, Path]:
    job = example()
    if stage == "model":
        del operation(job)["parameters"]["cut_feed_mm_per_min"]
    if stage == "ncx_words":
        job["program"]["name"] = "RECT FILLETS"
    job_file = job_folder(base / "job", '{"version": 1,' if stage == "file" else job)
    if stage == "dxf":
        (base / "job" / "part.dxf").unlink()
    out = base / "out"
    if stage == "output":
        out.mkdir()
        (out / "old.h").write_bytes(b"")
    return job_file, out


def _check(report: JobReport, out: Path, stage: str, fake: FakeRunNcx) -> None:
    failed = any(d.severity is Severity.ERROR or d.code == "CANCELLED" for d in report.diagnostics)
    if failed:
        assert report.nc_files == ()
    if report.ok:
        assert report.ncx_file is not None
        assert report.nc_files
    reached_ncx = stage in ("none", "no_ncx")
    if stage == "output":
        assert listing(out) == ["old.h"]
    elif not reached_ncx:
        assert listing(out) == []
    else:
        nc = [path.name for path in report.nc_files]
        assert listing(out) == sorted(["RECT_FILLETS.ncx", *nc])
        assert report.ok == (stage == "none" and fake.ok and not fake.cancel and bool(fake.files))
    for call in fake.calls:  # REQ-JOB-018: the working folder never outlives the run
        assert not call.work_dir.parent.exists()


@pytest.mark.req("REQ-JOB-001", "REQ-JOB-010", "REQ-JOB-016", "REQ-JOB-017", "REQ-JOB-018",
                 "REQ-JOB-019", "REQ-JOB-021")  # fmt: skip
@settings(max_examples=40, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(stage=st.sampled_from(_STAGES), outcome=_OUTCOMES)
def test_files_match_the_stage_reached(tmp_path: Path, stage: str, outcome: str) -> None:
    base = Path(tempfile.mkdtemp(dir=tmp_path))
    job_file, out = _folder(base, stage)
    fake = FakeRunNcx(files=() if outcome == "no_file" else ("RECT_FILLETS.h",),
                      ok=outcome != "failed", cancel=outcome == "cancelled")  # fmt: skip
    exe = base / ("no-ncx" if stage == "no_ncx" else "ncx")
    if stage != "no_ncx":
        exe.write_bytes(b"")
    registry = {STRATEGY_ID: Strategy(DECLARATIONS, profile_input, _plan(stage == "plan"))}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr("splintercam.job._output.run_ncx", fake)
        patch.setattr("splintercam.job._run.REGISTRY", registry)
        if stage == "write":
            patch.setattr(Path, "write_bytes", _refuse_write)
        report = run_job(job_file, out, ncx_executable=exe, ctx=make_context())
    _check(report, out, stage, fake)


def _refuse_write(self: Path, data: bytes) -> int:
    del self, data
    raise OSError(28, "No space left on device")
