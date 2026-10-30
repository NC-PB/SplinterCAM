# SPDX-License-Identifier: Apache-2.0
"""The exit code, one report per case (src/splintercam/apps/cli/SPEC.md, REQ-CLI-005;
DEC-CLI-002)."""

import pytest

from cli_fakes import FakeRunJob, diagnostic, report
from splintercam.apps.cli import main
from splintercam.job import Diagnostic, Severity

_RUN = ["run", "job.json", "--output", "out"]
_INFO = diagnostic("NCX_ROUNDED", Severity.INFO)
_WARNING = diagnostic("JOB_MACHINE_OVERRIDDEN", Severity.WARNING)
_ERROR = diagnostic("NCX_STEP_FAILED")
_CANCELLED = diagnostic("CANCELLED", Severity.WARNING)


@pytest.mark.req("REQ-CLI-005")
@pytest.mark.parametrize(
    ("diagnostics", "plain", "strict"),
    [
        ((), 0, 0),
        ((_INFO,), 0, 0),  # INFO never changes the code: NCX_ROUNDED passes --strict
        ((_INFO, _WARNING), 0, 1),
        ((_ERROR,), 1, 1),
        ((_WARNING, _ERROR), 1, 1),
        ((_CANCELLED,), 1, 1),  # a cancelled run has no program
        ((diagnostic("JOB_FILE_UNREADABLE"),), 2, 2),
        ((diagnostic("DXF_UNREADABLE"),), 2, 2),
        ((diagnostic("JOB_MACHINE_NOT_FOUND"),), 2, 2),
        ((_ERROR, diagnostic("JOB_MACHINE_NOT_FOUND")), 2, 2),  # 2 wins over 1, in any order
        ((diagnostic("DXF_UNREADABLE", Severity.INFO),), 0, 0),  # INFO never changes it
        ((diagnostic("JOB_FILE_UNREADABLE", Severity.WARNING),), 0, 1),
        ((diagnostic("JOB_FILE_INVALID"),), 1, 1),  # readable but wrong: the job's fault
        ((diagnostic("JOB_NCX_NOT_FOUND"),), 1, 1),
    ],
)
def test_the_exit_code_of_each_case(
    diagnostics: tuple[Diagnostic, ...], plain: int, strict: int, fake_run_job: FakeRunJob
) -> None:
    fake_run_job.report = report(*diagnostics)
    assert main(_RUN) == plain
    assert main([*_RUN, "--strict"]) == strict
    assert len(fake_run_job.calls) == 2  # REQ-CLI-002: one run_job call per run
