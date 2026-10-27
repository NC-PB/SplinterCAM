# SPDX-License-Identifier: Apache-2.0
"""`run_ncx`: the pinned `ncx` as a subprocess, step by step (REQ-NCX-018 to 025; research 27,
The ncx call in plan 0007; DEC-NCX-005, 007)."""

import subprocess
from dataclasses import dataclass

from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity

from ._messages import read_messages
from ._types import NcxCall, NcxProgram, NcxStep

_POLL_S = 0.05  # DEC-NCX-007: how often the wait for a step looks at ctx.cancel


@dataclass(frozen=True, slots=True)
class _Exit:
    code: int
    stdout: str
    stderr: str


def _arguments(step: NcxStep, call: NcxCall) -> list[str]:
    file, machine = str(call.ncx_file), str(call.machine_file)
    if step is NcxStep.FORMAT:
        return [str(call.executable), "format", "--check", file]
    if step is NcxStep.CHECK:
        return [str(call.executable), "check", file, "--machine", machine, "--strict"]
    return [
        str(call.executable),
        "compile",
        file,
        "--machine",
        machine,
        "--output",
        str(call.output_dir),
    ]


def _decode(output: bytes) -> str:
    return output.decode("utf-8", errors="replace")


def _run_step(step: NcxStep, call: NcxCall, ctx: Context) -> _Exit | OSError | None:
    # The step's exit, the OS error that kept it from starting, or None when cancelled.
    # communicate() reads both pipes to their end while it waits, so a full pipe never blocks
    # the child; a timeout loses no output (DEC-NCX-013).
    try:
        process = subprocess.Popen(
            _arguments(step, call),
            cwd=call.work_dir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        return error
    with process:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=_POLL_S)
                return _Exit(process.returncode, _decode(stdout), _decode(stderr))
            except subprocess.TimeoutExpired:
                if ctx.cancel.is_cancelled:
                    process.kill()
                    process.communicate()
                    return None


def run_ncx(call: NcxCall, program: NcxProgram, ctx: Context) -> Result[tuple[NcxStep, ...]]:
    """`ncx format --check`, `check --strict` and `compile` on `call`'s files, in `call.work_dir`;
    the value is the steps that ran, `ok` only when each exited 0 and no ERROR came. `compile`
    runs only after the other two passed (DEC-NCX-005); exit 1 is `NCX_STEP_FAILED`; another
    code or no process is `NCX_CALL_FAILED` and ends the call. Cancelled: no value.

    Implements: REQ-NCX-018 to 025.
    """
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
        found += read_messages(step, outcome.stderr, call.ncx_file, program.sections)
        if outcome.code == 1:
            difference = f":\n{outcome.stdout}" if step is NcxStep.FORMAT else ""
            message = f"ncx {step.value} exited with 1{difference}"
            found.append(Diagnostic("NCX_STEP_FAILED", Severity.ERROR, message, where))
        elif outcome.code != 0:
            message = f"ncx {step.value} exited with {outcome.code}"
            found.append(Diagnostic("NCX_CALL_FAILED", Severity.ERROR, message, where))
            break
    return Result(tuple(ran), tuple(found))
