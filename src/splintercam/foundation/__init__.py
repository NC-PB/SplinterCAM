# SPDX-License-Identifier: Apache-2.0
"""foundation: the shared vocabulary of every splintercam module (see SPEC.md)."""

from ._context import CancellationToken, Context, DebugSink
from ._result import Diagnostic, Result, Severity
from ._tolerance import ToleranceSet, nearly_equal

__all__ = [
    "CancellationToken",
    "Context",
    "DebugSink",
    "Diagnostic",
    "Result",
    "Severity",
    "ToleranceSet",
    "nearly_equal",
]
