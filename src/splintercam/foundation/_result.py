# SPDX-License-Identifier: Apache-2.0
"""Results with diagnostics: Severity, Diagnostic and Result."""

import enum
from dataclasses import dataclass


class Severity(enum.Enum):
    """How serious a `Diagnostic` is.

    INFO: an expected outcome worth a person knowing about (for example an empty region).
    WARNING: the result is usable, but degraded in some way worth checking.
    ERROR: no usable result; `Result.ok` is False regardless of whether a value is present.

    Implements: REQ-FND-004.
    """

    INFO = enum.auto()
    WARNING = enum.auto()
    ERROR = enum.auto()


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """One typed diagnostic attached to a `Result`, in place of a thrown exception.

    Attributes:
        code: an UPPER_SNAKE code identifying the situation, for example "OFFSET_EMPTY".
        severity: how serious this diagnostic is.
        message: a human-readable explanation.
        location: an optional human-readable location (a feature name, a loop index), or
            None when there is none.

    Implements: REQ-FND-004.
    """

    code: str
    severity: Severity
    message: str
    location: str | None = None


@dataclass(frozen=True, slots=True)
class Result[T]:
    """The outcome of a computation: an optional value plus ordered diagnostics.

    Attributes:
        value: the computed value, or None if the computation produced nothing usable.
        diagnostics: diagnostics in the order they were raised; never reordered. Coerced to a
            tuple in `__post_init__`, so a list or generator passed in cannot be mutated
            afterwards to change `ok` between calls.

    Postcondition: `ok` is True only when `value` is not None and no diagnostic has severity
    `ERROR` (module invariant: "ok" is consistent with its diagnostics).

    Implements: REQ-FND-004.
    """

    value: T | None
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        # Frozen dataclass: __setattr__ is disabled outside __init__/__post_init__. A list or
        # generator passed in as diagnostics is replaced here with an immutable tuple, so it
        # cannot be mutated afterwards to make `ok` change between calls.
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))

    @property
    def ok(self) -> bool:
        """True only if a value is present and no diagnostic has severity ERROR."""
        return self.value is not None and all(
            diagnostic.severity is not Severity.ERROR for diagnostic in self.diagnostics
        )
