# SPDX-License-Identifier: Apache-2.0
"""Records and programs for the ncx tests: research 22 test 1's profile as in
src/splintercam/ncx/SPEC.md, Example parts (T1 at 8000 1/min, cut 1200, plunge 300)."""

import math
from collections.abc import Sequence
from dataclasses import replace
from fractions import Fraction

import numpy as np

from cl_strategies import HEADER, Move, columns, profile_moves
from splintercam.cl import ClData, ClHeader, ClOperation, make_cl_data
from splintercam.foundation import Context, Diagnostic
from splintercam.ncx import NcxProgram, ProgramInfo, write_ncx
from splintercam.ncx._printer import to_steps, to_text

PROFILE = replace(HEADER, name="PROFILE_1", feed_classes=(("plunge", 300.0), ("cut", 1200.0)))
RECT_FILLETS = ProgramInfo("RECT_FILLETS", 1001)


def record(
    ctx: Context, *headers: ClHeader, moves: Sequence[Move] | None = None, work_offset: int = 1
) -> ClData:
    """One operation per header, each with `moves` (the profile when None)."""
    rows = profile_moves() if moves is None else moves
    operations = tuple(ClOperation(header, columns(rows)) for header in headers or (PROFILE,))
    return make_cl_data(work_offset, operations, ctx)


def written(ctx: Context, *headers: ClHeader, moves: Sequence[Move] | None = None) -> NcxProgram:
    """The program of `record`, which must be written without an error."""
    result = write_ncx(record(ctx, *headers, moves=moves), RECT_FILLETS, ctx)
    assert result.ok, result.diagnostics
    assert result.value is not None
    return result.value


def refused(
    ctx: Context, *headers: ClHeader, program: ProgramInfo = RECT_FILLETS
) -> tuple[Diagnostic, ...]:
    """The diagnostics of a refused program."""
    result = write_ncx(record(ctx, *headers), program, ctx)
    assert result.value is None
    return result.diagnostics


def printed(values: Sequence[float]) -> list[str]:
    """The printer's text of each value."""
    return [str(text) for text in to_text(to_steps(np.array(values, dtype=np.float64)))]


def exact_text(value: float) -> str:
    """Research 26, Number printer, in rational arithmetic: half away from zero to 10^-6,
    decided on the exact value; the oracle for the printer."""
    scaled = Fraction(value) * 10**6
    count = math.floor(abs(scaled) + Fraction(1, 2))
    whole, fraction = divmod(count, 10**6)
    digits = f"{fraction:06d}".rstrip("0") or "0"
    sign = "-" if scaled < 0 and count else ""
    return f"{sign}{whole}.{digits}"


def words(line: str) -> dict[str, str]:
    """A block's words, `X=5.0` as {"X": "5.0"}, a word without value as itself."""
    pairs = (word.partition("=") for word in line.split(" "))
    return {key: value for key, _, value in pairs}
