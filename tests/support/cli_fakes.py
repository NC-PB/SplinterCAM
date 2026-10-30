# SPDX-License-Identifier: Apache-2.0
"""A fake `run_job` for the cli tests and the reports they give it
(src/splintercam/apps/cli/SPEC.md, Test plan: `main` with a fake `run_job`)."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from splintercam.job import Diagnostic, JobReport, Severity


@dataclass
class FakeRunJob:
    """Stands in for `job.run_job`: records the arguments of each call, returns `report`."""

    report: JobReport = field(default_factory=lambda: JobReport((), None, None))
    calls: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])

    def __call__(self, job_file: Path, output_dir: Path, **options: Any) -> JobReport:
        self.calls.append({"job_file": job_file, "output_dir": output_dir, **options})
        return self.report


def report(*diagnostics: Diagnostic, ncx_file: Path | None = None,
           nc_files: tuple[Path, ...] = ()) -> JobReport:  # fmt: skip
    """A report of `diagnostics` and files, with no record."""
    return JobReport(diagnostics, None, ncx_file, nc_files)


def diagnostic(code: str, severity: Severity = Severity.ERROR, location: str | None = None,
               message: str = "what happened") -> Diagnostic:  # fmt: skip
    return Diagnostic(code, severity, message, location)
