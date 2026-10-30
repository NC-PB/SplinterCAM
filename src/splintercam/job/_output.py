# SPDX-License-Identifier: Apache-2.0
"""The output folder, the NCX file, and `ncx` in a temporary folder with its files moved only
after a clean run (REQ-JOB-010, 016 to 019; research 27, traps 3, 4, 6, test 5; DEC-JOB-005, 007,
008)."""

import shutil
import tempfile
from pathlib import Path

from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity
from splintercam.ncx import NcxCall, NcxProgram, run_ncx

type Found = list[Diagnostic]


def _error(code: str, message: str, where: Path) -> Diagnostic:
    return Diagnostic(code, Severity.ERROR, message, str(where))


def _refused(code: str, message: str, where: Path) -> Result[Path]:
    return Result(None, (_error(code, message, where),))


def prepare_output(output: Path) -> Result[Path]:
    """Stage 2: the output folder made with its parents, or refused when it holds anything
    (DEC-JOB-005: an NC program of an earlier run must not pass for this run's).

    Implements: REQ-JOB-010."""
    try:
        if output.exists() and not (output.is_dir() and not any(output.iterdir())):
            text = f"the output folder {output} is not an empty folder; name a new one"
            return _refused("JOB_OUTPUT_NOT_EMPTY", text, output)
        output.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        text = f"cannot make the output folder {output}: {error.strerror or error}"
        return _refused("JOB_OUTPUT_UNWRITABLE", text, output)
    return Result(output)


def write_ncx_file(output: Path, name: str, program: NcxProgram) -> Result[Path]:
    """Stage 8: `<output>/<program name>.ncx`, ASCII; a partial file removed after a failure.

    Implements: REQ-JOB-016."""
    path = output / f"{name}.ncx"  # research 27, trap 6: the stem is the program name
    try:
        path.write_bytes(program.text.encode("ascii"))
    except OSError as error:
        path.unlink(missing_ok=True)
        text = f"cannot write {path}: {error.strerror or error}"
        return _refused("JOB_OUTPUT_UNWRITABLE", text, path)
    return Result(path)


def _move(staging: Path, output: Path, found: Found) -> tuple[Path, ...]:
    # REQ-JOB-019: all or none; a file moved before a failure is removed again.
    moved: list[Path] = []
    try:
        for entry in sorted(staging.iterdir(), key=lambda p: p.name):  # by code point
            moved.append(Path(shutil.move(entry, output / entry.name)))
    except OSError as error:
        for path in moved:
            path.unlink(missing_ok=True)
        text = f"cannot move the NC files into {output}: {error}"
        found.append(_error("JOB_OUTPUT_UNWRITABLE", text, output))
        return ()
    if not moved:
        found.append(_error("JOB_NO_NC_FILE", "ncx compile passed but wrote no file", output))
    return tuple(moved)


def _call_ncx(call: NcxCall, program: NcxProgram, output: Path, ctx: Context,
              found: Found) -> tuple[Path, ...]:  # fmt: skip
    ran = run_ncx(call, program, ctx)
    found += ran.diagnostics
    if not ran.ok:
        return ()
    if ctx.cancel.is_cancelled:  # set after the last step: move nothing (REQ-JOB-021)
        found.append(CANCELLED)
        return ()
    return _move(call.output_dir, output, found)


def compile_ncx(executable: Path | None, ncx_file: Path, machine: Path, program: NcxProgram,
                ctx: Context) -> Result[tuple[Path, ...]]:  # fmt: skip
    """Stage 9: `ncx` in a new temporary folder holding the working and the staging folder,
    removed afterwards whatever happened; the compiled files moved into the NCX file's folder
    only after a clean run (DEC-JOB-007, 008).

    Implements: REQ-JOB-017, REQ-JOB-018, REQ-JOB-019."""
    if executable is None or not executable.is_file():
        what = "no ncx on the PATH" if executable is None else f"{executable} does not exist"
        text = f"{what}: the NCX file is written, no NC program"  # plan 0007, question 3
        return Result(None, (Diagnostic("JOB_NCX_NOT_FOUND", Severity.ERROR, text),))
    found: Found = []
    temporary = Path(tempfile.mkdtemp(prefix="splintercam-job-")).absolute()
    try:
        work, staging = temporary / "work", temporary / "staging"
        work.mkdir()
        staging.mkdir()
        call = NcxCall(executable, work, ncx_file, machine, staging)
        nc_files = _call_ncx(call, program, ncx_file.parent, ctx, found)
    finally:
        try:
            shutil.rmtree(temporary)
        except OSError as error:
            text = f"the temporary folder {temporary} could not be removed: {error}"
            found.append(Diagnostic("JOB_WORK_DIR_LEFT", Severity.WARNING, text, str(temporary)))
    return Result(nc_files, tuple(found))
