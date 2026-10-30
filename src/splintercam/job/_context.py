# SPDX-License-Identifier: Apache-2.0
"""The `Context` a run takes when the caller gives none (SPEC, Public interface)."""

import logging

import numpy as np
from numpy.typing import NDArray

from splintercam.foundation import TOLERANCE_DEFAULTS, CancellationToken, Context, ToleranceSet


class _NullSink:
    def add(self, name: str, kind: str, data: NDArray[np.float64]) -> None:
        del name, kind, data


def default_context() -> Context:
    """The tolerance set of the default tol, a new cancel token, no-op progress and debug sink,
    the logger `splintercam.job`, seed 0."""
    built = ToleranceSet.for_operation(TOLERANCE_DEFAULTS["chord_tol_finishing_mm"].default)
    if built.value is None:  # the defaults file is code: its default tol always builds
        raise ValueError(f"the default tol has no tolerance set: {built.diagnostics}")
    return Context(built.value, CancellationToken(), lambda _fraction: None,
                   logging.getLogger("splintercam.job"), _NullSink(), 0)  # fmt: skip
