# SPDX-License-Identifier: Apache-2.0
"""The cli tests' fixture: the fake `run_job` of tests/support/cli_fakes.py put where the cli
calls it (src/splintercam/apps/cli/SPEC.md, Test plan)."""

import pytest

from cli_fakes import FakeRunJob


@pytest.fixture
def fake_run_job(monkeypatch: pytest.MonkeyPatch) -> FakeRunJob:
    """A fake `run_job` returning an empty report; set its `report` per test."""
    fake = FakeRunJob()
    monkeypatch.setattr("splintercam.apps.cli._cli.run_job", fake)
    return fake
