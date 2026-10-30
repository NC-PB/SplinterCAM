# SPDX-License-Identifier: Apache-2.0
"""The output folder, the NCX file, and `ncx` in a temporary folder with its files moved only
after a clean run (REQ-JOB-010, 016 to 019; research 27, traps 3, 4, 6, test 5; DEC-JOB-005, 007,
008)."""

import functools
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity
from splintercam.ncx import NcxCall, NcxProgram, run_ncx


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
        _place(path, lambda partial: partial.write_bytes(program.text.encode("ascii")))
    except OSError as error:
        text = f"cannot write {path}: {error.strerror or error}"
        return _refused("JOB_OUTPUT_UNWRITABLE", text, path)
    return Result(path)


def _place(target: Path, write: Callable[[Path], object]) -> None:
    # DEC-JOB-013: written under a name no control loads, then renamed within its folder, which
    # is atomic: a crash or a full disk never leaves part of a file under the real name.
    partial = target.with_name(f".{target.name}.partial")
    try:
        write(partial)
        partial.replace(target)
    except OSError as error:  # the first reason kept; a partial file left is named
        left = "" if _removed(partial) else f"; {partial.name} left there, remove it by hand"
        raise OSError(f"{error.strerror or error}{left}") from error


def _roll_back(moved: list[Path]) -> str:
    left = [path.name for path in moved if not _removed(path)]
    return f"; left there, remove by hand: {', '.join(left)}" if left else ""


def _move(staging: Path, output: Path, found: list[Diagnostic], ctx: Context
          ) -> tuple[Path, ...]:  # fmt: skip
    # REQ-JOB-019: all or none; a file placed before a failure or a cancel is removed again
    # (DEC-JOB-011: a cancel wins, polled before each file and after the last).
    moved: list[Path] = []
    try:
        for entry in sorted(staging.iterdir(), key=lambda p: p.name):  # by code point
            target = output / entry.name
            if ctx.cancel.is_cancelled:
                break
            if entry.is_symlink() or not entry.is_file() or target.exists():
                raise OSError(f"{entry.name} is not a regular file, or is there already")
            _place(target, functools.partial(shutil.copyfile, entry))
            moved.append(target)
    except OSError as error:
        text = f"cannot move the NC files into {output}: {error}{_roll_back(moved)}"
        found.append(_error("JOB_OUTPUT_UNWRITABLE", text, output))
        return ()
    if ctx.cancel.is_cancelled:
        found.append(replace(CANCELLED, message=CANCELLED.message + _roll_back(moved)))
        return ()
    if not moved:
        found.append(_error("JOB_NO_NC_FILE", "ncx compile passed but wrote no file", output))
    return tuple(moved)


def _removed(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        return False
    return True


def _within(path: Path, folder: Path) -> bool:
    # `path` is `folder` or lies in it, links and case as the file system sees them (REQ-JOB-018).
    return any(p.exists() and p.samefile(folder) for p in (path, *path.parents))


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
    try:
        if _within(Path(tempfile.gettempdir()), ncx_file.parent):  # DEC-JOB-014
            raise OSError(f"{tempfile.gettempdir()} lies in the output folder; set TMPDIR or TEMP")
        temporary = Path(tempfile.mkdtemp(prefix="splintercam-job-"))
    except OSError as error:
        text = f"cannot make a temporary folder for ncx: {error}"
        return Result(None, (Diagnostic("JOB_WORK_DIR_UNWRITABLE", Severity.ERROR, text),))
    found: list[Diagnostic] = []
    nc_files: tuple[Path, ...] = ()
    try:
        work, staging = temporary / "work", temporary / "staging"
        work.mkdir()
        staging.mkdir()
    except OSError as error:
        text = f"cannot make the working folders for ncx: {error}"
        found.append(_error("JOB_WORK_DIR_UNWRITABLE", text, temporary))  # DEC-JOB-014
    else:
        ran = run_ncx(NcxCall(executable, work, ncx_file, machine, staging), program, ctx)
        found += ran.diagnostics
        if ran.ok:
            nc_files = _move(staging, ncx_file.parent, found, ctx)
    finally:
        try:
            shutil.rmtree(temporary)
        except OSError as error:
            text = f"the temporary folder {temporary} could not be removed: {error}"
            found.append(Diagnostic("JOB_WORK_DIR_LEFT", Severity.WARNING, text, str(temporary)))
    return Result(nc_files, tuple(found))
