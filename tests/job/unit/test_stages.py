# SPDX-License-Identifier: Apache-2.0
"""Stages 2 to 8 and the run as a whole (src/splintercam/job/SPEC.md, REQ-JOB-001, 010 to 016,
021, 022): the output folder, model, io, the registry and the plans, cl, the NCX file, cancelling
and determinism. The `ncx` stage has its own tests (tests/job/integration/)."""

import dataclasses
from pathlib import Path

import numpy as np
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
from splintercam.io import read_dxf_contour
from splintercam.job import JobReport, default_context, run_job
from splintercam.job._layout import read_job_file
from splintercam.job._registry import REGISTRY, Strategy, profile_input, relocate
from splintercam.model import check_job
from splintercam.ncx import ProgramInfo, write_ncx
from splintercam.strategies.profile import DECLARATIONS, STRATEGY_ID, ProfileInput, plan_profile


def _run(job_file: Path, out: Path, ctx: Context, exe: Path | None = None) -> JobReport:
    missing = out.parent / "no-ncx"
    return run_job(job_file, out, ncx_executable=exe or missing, ctx=ctx)


def _errors(report: JobReport) -> list[str]:
    return [d.code for d in report.diagnostics if d.severity is Severity.ERROR]


def _fake_registry(monkeypatch: pytest.MonkeyPatch, plan: object) -> None:
    fake = Strategy(DECLARATIONS, profile_input, plan)  # type: ignore[arg-type]
    monkeypatch.setattr("splintercam.job._run.REGISTRY", {STRATEGY_ID: fake})


# --- REQ-JOB-001: the stages and where they stop --------------------------------------------------


@pytest.mark.req("REQ-JOB-001")
def test_the_example_runs_every_stage_up_to_ncx(
    job_file: Path,
    tmp_path: Path,
    ctx: Context,
    fake_ncx: FakeRunNcx,
) -> None:
    report = _run(job_file, tmp_path / "out", ctx, fake_ncx.exe)
    assert report.ok, report.diagnostics
    assert codes(report.diagnostics) == ["JOB_INPUTS", "DXF_PART_SIZE"]
    assert report.cl_data is not None
    assert report.ncx_file == tmp_path / "out" / "RECT_FILLETS.ncx"
    assert report.nc_files == (tmp_path / "out" / "RECT_FILLETS.h",)
    assert listing(tmp_path / "out") == ["RECT_FILLETS.h", "RECT_FILLETS.ncx"]
    assert len(fake_ncx.calls) == 1


@pytest.mark.req("REQ-JOB-001", "REQ-JOB-011", "REQ-JOB-012")
@pytest.mark.parametrize(
    ("stage", "expected"),
    [
        (3, "PARAM_MISSING"),
        (4, "DXF_NO_UNITS"),
        (5, "PROFILE_TOO_DEEP"),
        (7, "NCX_PROGRAM_NAME_INVALID"),
    ],
)
def test_a_fault_stops_the_run_at_its_stage(
    tmp_path: Path,
    ctx: Context,
    stage: int,
    expected: str,
    fake_ncx: FakeRunNcx,
) -> None:
    job = example()
    insunits = 0 if stage == 4 else 4
    if stage == 3:
        del operation(job)["parameters"]["cut_feed_mm_per_min"]
    if stage == 5:
        operation(job)["parameters"]["z_bottom_mm"] = -19.0
        job["tools"][0]["flute_length_mm"] = 15.0
    if stage == 7:
        job["program"]["name"] = "RECT FILLETS"
    report = _run(job_folder(tmp_path / "job", job, insunits=insunits), tmp_path / "out", ctx,
                  fake_ncx.exe)  # fmt: skip
    assert expected in _errors(report)
    assert report.cl_data is None if stage < 7 else report.cl_data is not None
    assert (report.ncx_file, report.nc_files) == (None, ())
    assert listing(tmp_path / "out") == []
    assert fake_ncx.calls == []
    assert not report.ok


@pytest.mark.req("REQ-JOB-011")
def test_without_its_feeds_model_reports_param_missing_twice(tmp_path: Path, ctx: Context) -> None:
    job = example()
    del operation(job)["parameters"]["cut_feed_mm_per_min"]
    del operation(job)["parameters"]["plunge_feed_mm_per_min"]
    report = _run(job_folder(tmp_path / "job", job), tmp_path / "out", ctx)
    assert codes(report.diagnostics) == ["JOB_INPUTS", "PARAM_MISSING", "PARAM_MISSING"]


@pytest.mark.req("REQ-JOB-011")
def test_model_sees_the_example_job_without_a_diagnostic(job_file: Path) -> None:
    read = read_job_file(job_file, None, None)
    assert read.value is not None
    declarations = {sid: entry.declarations for sid, entry in REGISTRY.items()}
    checked = check_job(read.value.data, declarations, default_context())
    assert checked.ok
    assert checked.diagnostics == ()


@pytest.mark.req("REQ-JOB-012")
def test_the_job_unit_reads_a_dxf_without_units(tmp_path: Path, ctx: Context) -> None:
    job = example()
    job["part"]["unit"] = "mm"
    report = _run(job_folder(tmp_path / "job", job, insunits=0), tmp_path / "out", ctx)
    assert _errors(report) == ["JOB_NCX_NOT_FOUND"]


@pytest.mark.req("REQ-JOB-012")
def test_the_layer_is_passed_to_io(tmp_path: Path, ctx: Context) -> None:
    job = example()
    job["part"]["layer"] = "NOT_THERE"
    report = _run(job_folder(tmp_path / "job", job), tmp_path / "out", ctx)
    assert _errors(report) == ["DXF_LAYER_EMPTY"]


# --- REQ-JOB-010: the output folder ---------------------------------------------------------------


@pytest.mark.req("REQ-JOB-010")
def test_a_folder_that_is_not_empty_is_refused(
    job_file: Path, tmp_path: Path, ctx: Context
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    (out / "RECT_FILLETS.h").write_text("an old program", encoding="ascii")
    report = _run(job_file, out, ctx)
    assert codes(report.diagnostics) == ["JOB_INPUTS", "JOB_OUTPUT_NOT_EMPTY"]
    assert listing(out) == ["RECT_FILLETS.h"]
    assert (out / "RECT_FILLETS.h").read_text(encoding="ascii") == "an old program"
    assert report.cl_data is None


@pytest.mark.req("REQ-JOB-010")
def test_run_twice_into_one_folder(job_file: Path, tmp_path: Path, ctx: Context) -> None:
    _run(job_file, tmp_path / "out", ctx)
    again = _run(job_file, tmp_path / "out", default_context())
    assert _errors(again) == ["JOB_OUTPUT_NOT_EMPTY"]


@pytest.mark.req("REQ-JOB-010")
def test_a_file_at_the_path_is_refused(job_file: Path, tmp_path: Path, ctx: Context) -> None:
    (tmp_path / "out").write_bytes(b"x")
    report = _run(job_file, tmp_path / "out", ctx)
    assert _errors(report) == ["JOB_OUTPUT_NOT_EMPTY"]
    assert (tmp_path / "out").read_bytes() == b"x"


@pytest.mark.req("REQ-JOB-010")
def test_a_folder_that_cannot_be_made_is_unwritable(
    job_file: Path, tmp_path: Path, ctx: Context
) -> None:
    (tmp_path / "file").write_bytes(b"x")
    report = _run(job_file, tmp_path / "file" / "out", ctx)
    assert _errors(report) == ["JOB_OUTPUT_UNWRITABLE"]
    assert report.diagnostics[-1].location == str(tmp_path / "file" / "out")


@pytest.mark.req("REQ-JOB-010")
def test_an_empty_folder_and_new_parents_are_taken(
    job_file: Path, tmp_path: Path, ctx: Context
) -> None:
    (tmp_path / "empty").mkdir()
    assert _errors(_run(job_file, tmp_path / "empty", ctx)) == ["JOB_NCX_NOT_FOUND"]
    deep = tmp_path / "a" / "b" / "c"
    assert _errors(_run(job_file, deep, default_context())) == ["JOB_NCX_NOT_FOUND"]
    assert listing(deep) == ["RECT_FILLETS.ncx"]


# --- REQ-JOB-013 and 014: the registry and the plans ----------------------------------------------


@pytest.mark.req("REQ-JOB-013")
def test_the_registry_holds_the_profile() -> None:
    assert list(REGISTRY) == [STRATEGY_ID]
    entry = REGISTRY[STRATEGY_ID]
    assert entry.declarations is DECLARATIONS
    assert entry.plan is plan_profile
    with pytest.raises(TypeError):
        REGISTRY["pocket"] = entry  # type: ignore[index]


@pytest.mark.req("REQ-JOB-013")
def test_an_unknown_strategy_is_models_op_strategy_unknown(tmp_path: Path, ctx: Context) -> None:
    job = example()
    operation(job)["strategy"] = "pocket"
    report = _run(job_folder(tmp_path / "job", job), tmp_path / "out", ctx)
    assert _errors(report) == ["OP_STRATEGY_UNKNOWN"]


@pytest.mark.req("REQ-JOB-014")
def test_the_golden_jobs_profile_input_field_by_field(
    job_file: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[tuple[ProfileInput, Context]] = []

    def plan(task: ProfileInput, op_ctx: Context) -> Result[ClOperation]:
        seen.append((task, op_ctx))
        return plan_profile(task, op_ctx)

    _fake_registry(monkeypatch, plan)
    report = _run(job_file, tmp_path / "out", ctx)
    assert _errors(report) == ["JOB_NCX_NOT_FOUND"]
    read = read_job_file(job_file, None, None).value
    assert read is not None
    checked = check_job(read.data, {STRATEGY_ID: DECLARATIONS}, ctx).value
    assert checked is not None
    [(task, op_ctx)] = seen
    assert task.tool == checked.tools[0]
    assert task.stock == checked.setup.stock
    assert task.operation == checked.setup.operations[0]
    assert [name for name, _ in task.operation.parameters] == [d.name for d in DECLARATIONS]
    part = read_dxf_contour(job_file.parent / "part.dxf", None, None, ctx).value
    assert part is not None
    assert np.array_equal(
        task.contour.rows, part.loop.rows, equal_nan=True
    )  # io's loop, as read (REQ-JOB-012)
    assert np.array_equal(task.contour.ids, part.loop.ids)
    assert op_ctx.tolerances == ToleranceSet.for_operation(0.01).value
    assert op_ctx.cancel is ctx.cancel
    assert (op_ctx.logger, op_ctx.debug, op_ctx.seed) == (ctx.logger, ctx.debug, ctx.seed)


@pytest.mark.req("REQ-JOB-014")
def test_the_tool_is_found_by_its_number(
    tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = example()
    other = dict(job["tools"][0], number=7, diameter_mm=6.0)
    job["tools"].insert(0, other)
    seen: list[ProfileInput] = []

    def plan(task: ProfileInput, op_ctx: Context) -> Result[ClOperation]:
        seen.append(task)
        return plan_profile(task, op_ctx)

    _fake_registry(monkeypatch, plan)
    _run(job_folder(tmp_path / "job", job), tmp_path / "out", ctx)
    assert [(task.tool.number, task.tool.diameter_mm) for task in seen] == [(1, 10.0)]


@pytest.mark.req("REQ-JOB-014")
def test_every_operation_is_planned_and_both_failures_reported(
    tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    job = example()
    job["operations"].append(dict(operation(job), name="PROFILE_2"))
    names: list[str] = []

    def plan(task: ProfileInput, op_ctx: Context) -> Result[ClOperation]:
        del op_ctx
        names.append(task.operation.name)
        where = f"operation ({task.operation.name})"
        return Result(None, (Diagnostic("FAKE", Severity.ERROR, "no", where),))

    _fake_registry(monkeypatch, plan)
    report = _run(job_folder(tmp_path / "job", job), tmp_path / "out", ctx)
    assert names == ["PROFILE_1", "PROFILE_2"]
    assert [(d.code, d.location) for d in report.diagnostics if d.code == "FAKE"] == [
        ("FAKE", "operation 1 (PROFILE_1)"),
        ("FAKE", "operation 2 (PROFILE_2)"),
    ]
    assert report.cl_data is None
    assert listing(tmp_path / "out") == []


@pytest.mark.req("REQ-JOB-014")
@pytest.mark.parametrize(
    ("location", "expected"),
    [
        ("operation (PROFILE_1)", "operation 1 (PROFILE_1)"),
        ("operation (PROFILE_1), parameter z_bottom_mm",
         "operation 1 (PROFILE_1), parameter z_bottom_mm"),
        (None, "operation 1 (PROFILE_1)"),
        ("loop 2", "operation 1 (PROFILE_1): loop 2"),
        ("operation (PROFILE_2)", "operation 1 (PROFILE_1): operation (PROFILE_2)"),
    ],
)  # fmt: skip
def test_a_strategys_location_is_rewritten_to_models_form(
    location: str | None, expected: str
) -> None:
    found = Diagnostic("X", Severity.WARNING, "m", location)
    assert relocate(found, 1, "PROFILE_1") == dataclasses.replace(found, location=expected)


@pytest.mark.req("REQ-JOB-014")
def test_a_strategy_warning_is_kept_with_the_plan(
    tmp_path: Path, ctx: Context, job_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def plan(task: ProfileInput, op_ctx: Context) -> Result[ClOperation]:
        planned = plan_profile(task, op_ctx)
        warning = Diagnostic("FAKE_NOTE", Severity.WARNING, "kept", None)
        return Result(planned.value, (*planned.diagnostics, warning))

    _fake_registry(monkeypatch, plan)
    report = _run(job_file, tmp_path / "out", ctx)
    assert ("FAKE_NOTE", "operation 1 (PROFILE_1)") in [
        (d.code, d.location) for d in report.diagnostics
    ]
    assert report.ncx_file is not None


# --- REQ-JOB-015 and 016: the record and the NCX file ---------------------------------------------


@pytest.mark.req("REQ-JOB-015", "REQ-JOB-016")
def test_the_ncx_file_holds_the_records_text(job_file: Path, tmp_path: Path, ctx: Context) -> None:
    report = _run(job_file, tmp_path / "out", ctx)
    assert report.cl_data is not None
    assert report.cl_data.work_offset == 1
    assert [op.header.name for op in report.cl_data.operations] == ["PROFILE_1"]
    program = write_ncx(report.cl_data, ProgramInfo("RECT_FILLETS", 1001), ctx).value
    assert program is not None
    assert report.ncx_file is not None
    assert report.ncx_file == tmp_path / "out" / "RECT_FILLETS.ncx"
    assert report.ncx_file.read_bytes() == program.text.encode("ascii")


@pytest.mark.req("REQ-JOB-015")
def test_the_work_offset_and_program_come_from_the_job(tmp_path: Path, ctx: Context) -> None:
    job = example()
    job["setup"]["work_offset"] = 2
    job["program"] = {"name": "P7", "number": 7}
    report = _run(job_folder(tmp_path / "job", job), tmp_path / "out", ctx)
    assert report.cl_data is not None
    assert report.cl_data.work_offset == 2
    assert listing(tmp_path / "out") == ["P7.ncx"]
    text = (tmp_path / "out" / "P7.ncx").read_text(encoding="ascii")
    assert 'PROGRAM=BEGIN NAME="P7" NUMBER=7' in text
    assert "ORIGIN=2" in text


@pytest.mark.req("REQ-JOB-016")
def test_a_failed_write_removes_the_partial_file(
    job_file: Path, tmp_path: Path, ctx: Context, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(self: Path, data: bytes) -> int:
        assert self.name == ".RECT_FILLETS.ncx.partial"  # never the real name (DEC-JOB-013)
        with self.open("wb") as partial:
            partial.write(data[:10])
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Path, "write_bytes", broken)
    report = _run(job_file, tmp_path / "out", ctx)
    assert _errors(report) == ["JOB_OUTPUT_UNWRITABLE"]
    assert "No space left" in report.diagnostics[-1].message
    assert listing(tmp_path / "out") == []
    assert report.ncx_file is None
    assert report.cl_data is not None


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
