# SPDX-License-Identifier: Apache-2.0
"""Cooperative cancellation, debug capture and the per-run Context."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from ._tolerance import ToleranceSet


class CancellationToken:
    """A cooperative cancellation flag shared between Python and kernels.

    The only stateful type in `foundation`: every other value type here is an immutable
    dataclass (SPEC "Invariants"). Cancelling twice is fine, and a cancelled token never
    becomes uncancelled.

    Implements: REQ-FND-006.
    """

    def __init__(self) -> None:
        self._flag: NDArray[np.uint8] = np.zeros(1, dtype=np.uint8)
        # Owning array kept read-only at all times, not just its views: NumPy refuses to make a
        # view writeable when it does not own its data and no array in the chain is writeable,
        # so this is what keeps `flag` (below) permanently un-resettable from outside `cancel()`.
        self._flag.flags.writeable = False

    def cancel(self) -> None:
        """Request cancellation. Idempotent; safe to call more than once."""
        self._flag.flags.writeable = True
        self._flag[0] = 1
        self._flag.flags.writeable = False

    @property
    def is_cancelled(self) -> bool:
        """True once `cancel()` has been called at least once."""
        return bool(self._flag[0])

    @property
    def flag(self) -> NDArray[np.uint8]:
        """A one-element uint8 array kernels can poll (element 0) without calling into Python.

        The C++ side reads element 0 through a `const volatile std::uint8_t*` (see
        `src/splintercam/geometry2d/kernel/offset.cpp` for a consumer), polling it between chunks
        of work instead of calling back into Python.

        The returned array is a read-only view onto the token's own memory, which is itself
        kept read-only outside `cancel()`: it reflects a later `cancel()` call, and writing
        through it raises, so a cancelled token cannot be reset by accident. Code that reaches
        the owning array (`flag.base`) could still make it writeable on purpose; Python offers
        no way to prevent that without leaving NumPy (SPEC, open questions).

        One-shot: create a new `CancellationToken` per job; it does not cross process
        boundaries (pickling copies the underlying array, so a cancellation in one process is
        not seen by another).
        """
        view = self._flag.view()
        view.flags.writeable = False
        return view


class DebugSink(Protocol):
    """A sink for named debug arrays a computation wants to expose for inspection."""

    def add(self, name: str, kind: str, data: NDArray[np.float64]) -> None:
        """Record one named array of `kind` for inspection.

        `data` is an (n, 2) or (n, 3) float64 array of coordinates in millimetres. `kind`
        names how to draw it, for example "points", "polyline" or "loop".
        """
        ...


@dataclass(frozen=True, slots=True)
class Context:
    """Everything one computation needs, threaded explicitly instead of read from globals.

    Attributes:
        tolerances: the tolerance budget for this computation.
        cancel: the cancellation token to poll during long-running work.
        progress: reports fractional completion from 0.0 to 1.0.
        logger: where this computation logs decisions worth a person's attention.
        debug: where this computation can expose named debug arrays.
        seed: a non-negative int seed, passed to `numpy.random.default_rng` for any random
            numbers this computation needs.

    No module reads any of these from global state (module invariant, docs/dev/04
    "State and concurrency").

    Implements: REQ-FND-005.
    """

    tolerances: ToleranceSet
    cancel: CancellationToken
    progress: Callable[[float], None]
    logger: logging.Logger
    debug: DebugSink
    seed: int
