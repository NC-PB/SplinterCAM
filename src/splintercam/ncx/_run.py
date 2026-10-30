# SPDX-License-Identifier: Apache-2.0
"""`run_ncx`: the pinned `ncx` as a subprocess, step by step (REQ-NCX-018 to 025; research 27,
The ncx call in plan 0007; DEC-NCX-005, 007)."""

import subprocess
from dataclasses import fields
from pathlib import Path

from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity

from ._messages import read_messages
from ._types import NcxCall, NcxProgram, NcxStep

_POLL_S = 0.05  # DEC-NCX-007: how often the wait for a step looks at ctx.cancel


def _arguments(step: NcxStep, call: NcxCall) -> list[str | Path]:
    file, machine = call.ncx_file, call.machine_file
    if step is NcxStep.FORMAT:
        return [call.executable, "format", "--check", file]
    if step is NcxStep.CHECK:
        return [call.executable, "check", file, "--machine", machine, "--strict"]
    return [call.executable, "compile", file, "--machine", machine, "--output", call.output_dir]


def _run_step(
    step: NcxStep, call: NcxCall, ctx: Context
) -> subprocess.CompletedProcess[str] | OSError | None:
    # None when cancelled. communicate() drains both pipes; a timeout loses no output (DEC-NCX-013).
    try:
        process = subprocess.Popen(
            _arguments(step, call),
            cwd=call.work_dir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as error:
        return error
    with process:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=_POLL_S)
                return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                if ctx.cancel.is_cancelled:
                    process.kill()
                    process.communicate()
                    return None


def run_ncx(call: NcxCall, program: NcxProgram, ctx: Context) -> Result[tuple[NcxStep, ...]]:
    """`ncx format --check`, `check --strict` and `compile` on `call`'s files, in `call.work_dir`;
    the value is the steps that ran (none when cancelled). A relative path in `call` raises
    `ValueError` (a precondition, as DEC-CL-002).

    Implements: REQ-NCX-018 to 025, 027.
    """
    relative = [
        name
        for name, path in ((f.name, getattr(call, f.name)) for f in fields(call))
        if not path.is_absolute()
    ]
    if relative:
        raise ValueError(f"ncx call: REQ-NCX-018: paths not absolute: {', '.join(relative)}")
    found: list[Diagnostic] = []
    ran: list[NcxStep] = []
    for step in NcxStep:
        if ctx.cancel.is_cancelled:
            return Result(None, (*found, CANCELLED))
        if step is NcxStep.COMPILE and any(d.severity is Severity.ERROR for d in found):
            break
        where = f"ncx {step.value}"
        outcome = _run_step(step, call, ctx)
        if outcome is None:
            return Result(None, (*found, CANCELLED))
        if isinstance(outcome, OSError):
            message = f"ncx {step.value} could not be started: {outcome}"
            found.append(Diagnostic("NCX_CALL_FAILED", Severity.ERROR, message, where))
            break
        ran.append(step)
        ctx.logger.debug("ncx %s stdout:\n%s", step.value, outcome.stdout)
        found += read_messages(step, outcome.stderr, call, program.sections)
        if outcome.returncode == 1:
            difference = f":\n{outcome.stdout}" if step is NcxStep.FORMAT else ""
            message = f"ncx {step.value} exited with 1{difference}"
            found.append(Diagnostic("NCX_STEP_FAILED", Severity.ERROR, message, where))
        elif outcome.returncode != 0:
            message = f"ncx {step.value} exited with {outcome.returncode}"
            found.append(Diagnostic("NCX_CALL_FAILED", Severity.ERROR, message, where))
            break
    if ctx.cancel.is_cancelled:  # set while the last step ran
        return Result(None, (*found, CANCELLED))
    return Result(tuple(ran), tuple(found))
