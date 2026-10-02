# SPDX-License-Identifier: Apache-2.0
"""Test-suite setup: Hypothesis profiles and requirement IDs as keywords (docs/dev/06)."""

import logging
import os

import numpy as np
import pytest
from hypothesis import settings
from numpy.typing import NDArray

from splintercam.foundation import CancellationToken, Context, ToleranceSet

# print_blob: a failing property test prints what is needed to replay it (docs/dev/06, rule 5).
# CI sets HYPOTHESIS_PROFILE=ci, Hypothesis's built-in profile: derandomised, no deadline, and it
# prints the blob too.
settings.register_profile("dev", print_blob=True)
# Plan 0001, step 2's "property tests pass with 10 000 cases each" run. deadline=None because a
# 10 000-example run is long enough that a per-example wall-clock budget makes it flaky, not
# because any single example is slow. Loaded only with HYPOTHESIS_PROFILE=thorough (opt-in; the
# load line below already reads that variable).
settings.register_profile("thorough", max_examples=10_000, print_blob=True, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Let `tools/test-one <module> REQ_OFF_003` select the tests marked req("REQ-OFF-003")."""
    for item in items:
        for marker in item.iter_markers(name="req"):
            for requirement_id in marker.args:
                item.extra_keyword_matches.add(str(requirement_id))
                item.extra_keyword_matches.add(str(requirement_id).replace("-", "_"))


class _RecordingDebugSink:
    """A `DebugSink` (splintercam.foundation) that keeps what was added, for tests to inspect."""

    def __init__(self) -> None:
        self.added: list[tuple[str, str, NDArray[np.float64]]] = []

    def add(self, name: str, kind: str, data: NDArray[np.float64]) -> None:
        self.added.append((name, kind, data))


@pytest.fixture
def progress_log() -> list[float]:
    """The list a test's `Context.progress` callback appends fractions to."""
    return []


@pytest.fixture
def debug_sink() -> _RecordingDebugSink:
    """The recording `DebugSink` a test's `Context.debug` records into."""
    return _RecordingDebugSink()


@pytest.fixture
def ctx(progress_log: list[float], debug_sink: _RecordingDebugSink) -> Context:
    """A `Context` for tests: real tolerances where research gives them, placeholders elsewhere."""
    tolerances = ToleranceSet(
        length_eps_mm=1e-6,  # RESEARCH 01, "Tolerances".
        angle_eps_rad=1e-9,  # PLACEHOLDER: no default chosen yet (foundation SPEC, open questions).
        chord_tol_mm=0.01,  # RESEARCH 01, "Tolerances".
        # PLACEHOLDER: the geometry2d SPEC suggests 30 % for the offset stage.
        stage_shares={"offset": 0.3},
    )
    return Context(
        tolerances=tolerances,
        cancel=CancellationToken(),
        progress=progress_log.append,
        logger=logging.getLogger("splintercam.tests"),
        debug=debug_sink,
        seed=0,
    )
