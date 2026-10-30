# SPDX-License-Identifier: Apache-2.0
"""`run_job`: the nine stages of REQ-JOB-001 in order, stopping after the first with an error or a
cancel, and the report (DEC-JOB-001, 002)."""

import contextlib
from dataclasses import dataclass, replace
from pathlib import Path

from splintercam.cl import ClData, ClOperation, make_cl_data
from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity, ToleranceSet
from splintercam.geometry2d import CurveRows
from splintercam.io import read_dxf_contour
from splintercam.model import JobData, check_job
from splintercam.ncx import write_ncx

from ._context import default_context
from ._layout import absolute, read_job_file
from ._output import compile_ncx, prepare_output, write_ncx_file
from ._registry import REGISTRY, relocate


@dataclass(frozen=True, slots=True)
class JobReport:
    """What one run did: every stage's diagnostics in stage order, the record, the files."""

    diagnostics: tuple[Diagnostic, ...]
    cl_data: ClData | None  # the record of stage 6, for the golden checks
    ncx_file: Path | None  # the NCX file written, or None
    nc_files: tuple[Path, ...] = ()  # the compiled files in the output folder, by code point

    @property
    def ok(self) -> bool:
        """No ERROR and no `CANCELLED` (DEC-JOB-001: a cancelled run has no program)."""
        return not any(d.severity is Severity.ERROR or d.code == CANCELLED.code
                       for d in self.diagnostics)  # fmt: skip


class _Stopped(Exception):  # noqa: N818 (a control signal: the run ends here, not an error)
    pass


class _Run:
    """One run's diagnostics and files so far; `take` ends the run after a stage that reports an
    error or after a cancel, which it reports once (REQ-JOB-001, 021)."""

    def __init__(self, ctx: Context, strict: bool) -> None:
        self.ctx = ctx
        self.strict = strict  # a warning withholds the NC program (AQ-040 (b))
        self.found: list[Diagnostic] = []
        self.cl_data: ClData | None = None
        self.ncx_file: Path | None = None
        self.nc_files: tuple[Path, ...] = ()

    def poll(self) -> None:
        if self.ctx.cancel.is_cancelled and all(d.code != CANCELLED.code for d in self.found):
            self.found.append(CANCELLED)
        if self.ctx.cancel.is_cancelled or any(d.severity is Severity.ERROR for d in self.found):
            raise _Stopped

    def take[T](self, result: Result[T]) -> T:
        self.found += result.diagnostics
        self.poll()
        if result.value is None:
            raise _Stopped
        return result.value


def _plan_all(job: JobData, contour: CurveRows, ctx: Context) -> Result[tuple[ClOperation, ...]]:
    # Stage 5: every operation planned in the user's order before an error stops the run
    # (DEC-JOB-002), each with its own tolerance set and its locations in model's form.
    planned: list[ClOperation] = []
    found: list[Diagnostic] = []
    for index, operation in enumerate(job.setup.operations, 1):
        if ctx.cancel.is_cancelled:
            break
        strategy = REGISTRY[operation.strategy]
        tolerances = ToleranceSet.for_operation(operation.tol_mm).value
        if tolerances is None:  # check_job built it (REQ-MDL-016)
            raise ValueError(f"operation {index}: tol {operation.tol_mm!r} has no tolerance set")
        task = strategy.build(operation, contour, job)
        result = strategy.plan(task, replace(ctx, tolerances=tolerances))
        found += (relocate(d, index, operation.name) for d in result.diagnostics)
        if result.value is not None:
            planned.append(result.value)
        elif not ctx.cancel.is_cancelled and all(d.severity is not Severity.ERROR for d in found):
            raise ValueError(f"operation {index}: the strategy gave no value and no error")
    return Result(tuple(planned), tuple(found))


def _stages(run: _Run, job_file: Path, output_dir: Path, machine_file: Path | None,
            ncx_executable: Path | None) -> None:  # fmt: skip
    run.poll()
    read = run.take(read_job_file(job_file, machine_file, ncx_executable))
    output = run.take(prepare_output(absolute(output_dir)))
    declarations = {sid: strategy.declarations for sid, strategy in REGISTRY.items()}
    job = run.take(check_job(read.data, declarations, run.ctx))
    part = run.take(read_dxf_contour(read.dxf, read.layer, read.unit, run.ctx))
    operations = run.take(_plan_all(job, part.loop, run.ctx))
    run.cl_data = run.take(Result(make_cl_data(job.setup.work_offset, operations, run.ctx)))
    program = run.take(write_ncx(run.cl_data, read.program, run.ctx))
    written = write_ncx_file(output, read.program.name, program)
    run.ncx_file = written.value  # named even when a cancel comes now: the file is there
    ncx_file = run.take(written)
    # The last stage: a cancel after it stops nothing more (REQ-JOB-021), so no poll.
    compiled = compile_ncx(
        read, ncx_file, program, run.ctx, tuple(run.found) if run.strict else None
    )
    run.found += compiled.diagnostics
    run.nc_files = compiled.value or ()


def run_job(  # noqa: PLR0913 (the SPEC's reviewed interface; `strict` from Peter, AQ-040 (b))
            job_file: Path, output_dir: Path, *, ncx_executable: Path | None = None,
            machine_file: Path | None = None, ctx: Context | None = None,
            strict: bool = False) -> JobReport:  # fmt: skip
    """Run the job of `job_file` into `output_dir`: the NCX file and, after a clean `ncx` run,
    the NC program. `machine_file` overrides the job's machine; `ncx_executable` None takes
    `ncx` from the PATH; `strict` withholds the NC program after any WARNING (AQ-040 (b)). A
    `ValueError` from `cl` or `ncx` is a producer's bug and not caught.

    Implements: REQ-JOB-001, REQ-JOB-011 to 015, REQ-JOB-020 to 022."""
    run = _Run(default_context() if ctx is None else ctx, strict)
    with contextlib.suppress(_Stopped):
        _stages(run, job_file, output_dir, machine_file, ncx_executable)
    return JobReport(tuple(run.found), run.cl_data, run.ncx_file, run.nc_files)
