# SPDX-License-Identifier: Apache-2.0
"""Job folders for the job tests (src/splintercam/job/SPEC.md, Test plan): the golden case's job
file as a dict to change, written with its DXF and a stand-in machine file into a folder, and a
fake `run_ncx` that `job` calls instead of the real one (DEC-JOB-009)."""

import copy
import importlib.util
import json
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity
from splintercam.ncx import NcxCall, NcxProgram, NcxStep

CASE = Path(__file__).parents[2] / "testdata" / "zoo" / "profile-rectangle-fillets"
MACHINE = "heidenhain-itnc530.toml"

type Job = dict[str, Any]


def example() -> Job:
    """The golden case's `job.json` as a dict, a fresh copy each call."""
    return copy.deepcopy(json.loads((CASE / "job.json").read_text(encoding="utf-8")))


def operation(job: Job, index: int = 0) -> dict[str, Any]:
    """The job's operation `index` (from 0), to change in place."""
    return job["operations"][index]


def _make_part() -> Callable[[Path, int], None]:
    spec = importlib.util.spec_from_file_location("make_part", CASE / "make_part.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    writes, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ in testdata
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = writes
    return module.write_part


write_part = _make_part()


def job_folder(folder: Path, job: Job | str | bytes | None = None, *, insunits: int = 4) -> Path:
    """`folder` with `job.json` (the example, a dict as JSON, or the text or bytes given),
    `part.dxf` and an empty stand-in `heidenhain-itnc530.toml`; the job file's path."""
    folder.mkdir(parents=True, exist_ok=True)
    if insunits == 4:
        shutil.copyfile(CASE / "part.dxf", folder / "part.dxf")
    else:
        write_part(folder / "part.dxf", insunits)
    (folder / MACHINE).write_bytes(b"")
    content = example() if job is None else job
    if isinstance(content, dict):
        content = json.dumps(content, indent=2)
    if isinstance(content, str):
        content = content.encode("utf-8")
    job_file = folder / "job.json"
    job_file.write_bytes(content)
    return job_file


def codes(diagnostics: tuple[Diagnostic, ...]) -> list[str]:
    return [d.code for d in diagnostics]


def listing(folder: Path) -> list[str]:
    """The names in `folder`, sorted; [] when it does not exist."""
    return sorted(p.name for p in folder.iterdir()) if folder.exists() else []


STEP_FAILED = Diagnostic("NCX_STEP_FAILED", Severity.ERROR, "ncx check exited with 1", "ncx check")


@dataclass
class FakeRunNcx:
    """Stands in for `ncx.run_ncx`: records each call and what its two folders held, writes
    `files` into the staging folder, then returns as told (ok, failed or cancelled)."""

    exe: Path = Path("ncx")  # the conftest fixture gives a file that exists
    files: tuple[str, ...] = ("RECT_FILLETS.h",)
    ok: bool = True
    cancel: bool = False
    diagnostics: tuple[Diagnostic, ...] = ()
    calls: list[NcxCall] = field(default_factory=list[NcxCall])
    seen: list[tuple[list[str], list[str]]] = field(
        default_factory=list[tuple[list[str], list[str]]]
    )

    def __call__(self, call: NcxCall, program: NcxProgram, ctx: Context
                 ) -> Result[tuple[NcxStep, ...]]:  # fmt: skip
        del program
        self.calls.append(call)
        self.seen.append((listing(call.work_dir), listing(call.output_dir)))
        for name in self.files:  # a name ending in "/" is a folder
            if name.endswith("/"):
                (call.output_dir / name).mkdir()
            else:
                (call.output_dir / name).write_text("; fake\n", encoding="ascii")
        if self.cancel:
            ctx.cancel.cancel()
            return Result(None, (*self.diagnostics, CANCELLED))
        if not self.ok:
            return Result(None, (*self.diagnostics, STEP_FAILED))
        return Result(tuple(NcxStep), self.diagnostics)
