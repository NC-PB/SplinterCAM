# SPDX-License-Identifier: Apache-2.0
"""The exit code over generated reports, and stdout naming files only for exit code 0
(src/splintercam/apps/cli/SPEC.md, REQ-CLI-005, Invariants)."""

import contextlib
import io
import json
from pathlib import Path
from unittest import mock

import pytest
from hypothesis import given
from hypothesis import strategies as st

from cli_fakes import FakeRunJob, report
from splintercam.apps.cli import main
from splintercam.job import Diagnostic, JobReport, Severity

_INPUT = ("JOB_FILE_UNREADABLE", "DXF_UNREADABLE", "JOB_MACHINE_NOT_FOUND")
_CODES = st.sampled_from([*_INPUT, "CANCELLED", "NCX_ROUNDED", "JOB_INPUTS", "NCX_STEP_FAILED"])
_TEXT = st.text(max_size=8)
_DIAGNOSTIC = st.builds(Diagnostic, _CODES, st.sampled_from(Severity), _TEXT, st.none() | _TEXT)
_FILES = (Path("out/A.ncx").absolute(), (Path("out/A.h").absolute(),))


def _expected(diagnostics: tuple[Diagnostic, ...], strict: bool) -> int:
    # REQ-CLI-005 as written, an oracle independent of the code's form; the codes of 2 as
    # errors, since INFO never changes the code (DEC-CLI-003).
    if any(d.code in _INPUT and d.severity is Severity.ERROR for d in diagnostics):
        return 2
    if any(d.severity is Severity.ERROR or d.code == "CANCELLED" for d in diagnostics):
        return 1
    if strict and any(d.severity is Severity.WARNING for d in diagnostics):
        return 1
    return 0


def _run(fake: JobReport, argv: list[str]) -> tuple[int, str, str]:
    # No capsys or monkeypatch: Hypothesis refuses function-scoped fixtures.
    out, err = io.StringIO(), io.StringIO()
    with (mock.patch("splintercam.apps.cli._cli.run_job", FakeRunJob(fake)),
          contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):  # fmt: skip
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


@pytest.mark.req("REQ-CLI-005")
@pytest.mark.req("REQ-CLI-003")
@pytest.mark.req("REQ-CLI-004")
@given(diagnostics=st.lists(_DIAGNOSTIC, max_size=5).map(tuple), strict=st.booleans(),
       as_json=st.booleans())  # fmt: skip
def test_the_exit_code_is_a_function_of_the_report_and_strict(
    diagnostics: tuple[Diagnostic, ...], strict: bool, as_json: bool
) -> None:
    argv = ["run", "job.json", "--output", "out", *(["--strict"] if strict else []),
            *(["--json"] if as_json else [])]  # fmt: skip
    expected = _expected(diagnostics, strict)
    code, out, err = _run(report(*diagnostics, ncx_file=_FILES[0], nc_files=_FILES[1]), argv)
    assert code == expected
    if as_json:
        assert err == ""
        parsed = json.loads(out)
        assert parsed["exit_code"] == expected
        named = [parsed["ncx_file"], *parsed["nc_files"]]
        assert named == ([str(_FILES[0]), str(_FILES[1][0])] if expected == 0 else [None])
        assert [d["message"] for d in parsed["diagnostics"]] == [d.message for d in diagnostics]
    else:
        assert (out != "") == (expected == 0)
        # One line per diagnostic, whatever the generated text holds (REQ-CLI-003).
        assert len(err.splitlines()) == len(diagnostics)
        assert [line.split(" ", 2)[1].rstrip(":") for line in err.splitlines()] == [
            d.code for d in diagnostics]  # fmt: skip
