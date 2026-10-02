# SPDX-License-Identifier: Apache-2.0
"""foundation: the shared vocabulary of every splintercam module (see SPEC.md)."""

from ._context import CancellationToken, Context, DebugSink
from ._defaults import TOLERANCE_DEFAULTS, DeclaredParameter
from ._result import Diagnostic, Result, Severity
from ._tolerance import BUDGET_PARTS, ToleranceSet, nearly_equal

__all__ = [
    "BUDGET_PARTS",
    "TOLERANCE_DEFAULTS",
    "CancellationToken",
    "Context",
    "DebugSink",
    "DeclaredParameter",
    "Diagnostic",
    "Result",
    "Severity",
    "ToleranceSet",
    "nearly_equal",
]
