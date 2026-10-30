# SPDX-License-Identifier: Apache-2.0
"""The job tests' fixtures: a job folder, an `ncx` executable that exists, and the fake `run_ncx`
of tests/support/job_files.py put where `job` calls it (DEC-JOB-012)."""

from pathlib import Path

import pytest

from job_files import FakeRunNcx, job_folder


@pytest.fixture
def job_file(tmp_path: Path) -> Path:
    """The golden case's job, DXF and a stand-in machine file in `tmp_path / "job"`."""
    return job_folder(tmp_path / "job")


@pytest.fixture
def ncx_exe(tmp_path: Path) -> Path:
    """A file standing for the `ncx` executable; only the fake `run_ncx` is ever given it."""
    path = tmp_path / "bin" / "ncx"
    path.parent.mkdir()
    path.write_bytes(b"")
    return path


@pytest.fixture
def fake_ncx(monkeypatch: pytest.MonkeyPatch, ncx_exe: Path) -> FakeRunNcx:
    """A fake `run_ncx` that writes `RECT_FILLETS.h` and passes, its `exe` a file that exists;
    change its fields per test."""
    fake = FakeRunNcx(exe=ncx_exe)
    monkeypatch.setattr("splintercam.job._output.run_ncx", fake)
    return fake
