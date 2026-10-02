# SPDX-License-Identifier: Apache-2.0
"""Shared runner for the tools/ commands: steps, timing, exit codes and the summary line.

The contract every command follows (exit codes, last line = summary, reproduce commands) is in
tools/README.md, "Conventions for every command".
"""

import enum
import json
import shlex
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2


class Status(enum.StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True, slots=True)
class StepResult:
    """One step of a command. `detail` is the reproduce command of a failure or a skip reason."""

    name: str
    status: Status
    seconds: float
    detail: str = ""


class UsageError(Exception):
    """Wrong arguments or a missing tool; the command exits with EXIT_USAGE."""


def run_step(name: str, argv: Sequence[str], *, reproduce: str) -> StepResult:
    """Run one external command from the repository root, with its output going to the console."""
    executable = shutil.which(argv[0])
    if executable is None:
        raise UsageError(f"{argv[0]} not found; run tools/bootstrap")
    print(f"==> {name}: {shlex.join(argv)}", flush=True)
    start = time.perf_counter()
    completed = subprocess.run([executable, *argv[1:]], cwd=ROOT, check=False)
    seconds = time.perf_counter() - start
    if completed.returncode == 0:
        return StepResult(name, Status.PASS, seconds)
    return StepResult(name, Status.FAIL, seconds, f"reproduce: {reproduce}")


def skip(name: str, reason: str) -> StepResult:
    print(f"==> {name}: skipped ({reason})", flush=True)
    return StepResult(name, Status.SKIP, 0.0, reason)


def git_files(*args: str) -> list[Path]:
    """Existing files named by `git <args>` (paths relative to the root), without duplicates."""
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    )
    names = sorted({line for line in completed.stdout.splitlines() if line})
    return [ROOT / name for name in names if (ROOT / name).is_file()]


def summary_line(command: str, results: Sequence[StepResult]) -> str:
    failed = [r.name for r in results if r.status is Status.FAIL]
    skipped = [r.name for r in results if r.status is Status.SKIP]
    passed = sum(1 for r in results if r.status is Status.PASS)
    seconds = sum(r.seconds for r in results)
    parts = [f"{passed} of {len(results)} steps passed"]
    if skipped:
        parts.append(f"skipped: {', '.join(skipped)}")
    if failed:
        return f"{command}: FAIL ({', '.join(failed)}; {'; '.join(parts)}; {seconds:.1f} s)"
    return f"{command}: PASS ({'; '.join(parts)}; {seconds:.1f} s)"


def finish(command: str, results: Sequence[StepResult], *, as_json: bool = False) -> int:
    """Print the step table and the summary as the last line; return the exit code."""
    print()
    for r in results:
        print(f"{r.status:<4}  {r.name:<18} {r.seconds:7.1f} s  {r.detail}".rstrip())
    summary = summary_line(command, results)
    if as_json:
        steps = [
            {
                "name": r.name,
                "status": str(r.status),
                "seconds": round(r.seconds, 2),
                "detail": r.detail,
            }
            for r in results
        ]
        print(json.dumps({"command": command, "summary": summary, "steps": steps}))
    else:
        print(summary)
    return EXIT_FAILED if any(r.status is Status.FAIL for r in results) else EXIT_OK


def usage_error(command: str, error: UsageError) -> int:
    print(f"{command}: ERROR ({error})")
    return EXIT_USAGE
