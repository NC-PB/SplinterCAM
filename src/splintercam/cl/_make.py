# SPDX-License-Identifier: Apache-2.0
"""The validating entries: `make_operation` and `make_cl_data` (REQ-CL-018, 020; DEC-CL-002)."""

from splintercam.foundation import Context

from ._header import header_breach
from ._moves import column_breach, move_breach, read_only_copy
from ._types import ClData, ClHeader, ClMoves, ClOperation


def _refusal(name: str, requirement: str, detail: str) -> ValueError:
    return ValueError(f"operation {name!r}: {requirement}: {detail}")


def make_operation(header: ClHeader, moves: ClMoves, ctx: Context) -> ClOperation:
    """The operation with read-only copies of `moves`, or `ValueError` naming the operation, the
    first rule broken and its first move (REQ-CL-020).

    Implements: REQ-CL-002 to 017, REQ-CL-019 to 021.
    """
    field = header_breach(header)
    if field is not None:
        value = getattr(header, field)
        raise _refusal(header.name, "REQ-CL-017", f"header field {field} out of range: {value!r}")
    wrong_column = column_breach(moves)
    if wrong_column is not None:
        raise _refusal(header.name, "REQ-CL-004", wrong_column)
    held = read_only_copy(moves)
    breach = move_breach(header, held, ctx)
    if breach is not None:
        requirement, move, text = breach
        raise _refusal(header.name, requirement, f"move {move}: {text}")
    return ClOperation(header, held)


def make_cl_data(work_offset: int, operations: tuple[ClOperation, ...], ctx: Context) -> ClData:
    """One setup's record, every operation rebuilt through `make_operation` (REQ-CL-018), or
    `ValueError` in the order of REQ-CL-020.

    Implements: REQ-CL-001, REQ-CL-018, REQ-CL-019, REQ-CL-020.
    """
    if work_offset < 1:
        raise ValueError(f"cl data: REQ-CL-018: work offset {work_offset} is below 1")
    if not operations:
        raise ValueError("cl data: REQ-CL-018: no operation")
    rebuilt = tuple(make_operation(op.header, op.moves, ctx) for op in operations)
    names = [operation.header.name for operation in rebuilt]
    repeat = next((i for i, name in enumerate(names) if name in names[:i]), None)
    if repeat is not None:
        raise _refusal(names[repeat], "REQ-CL-018", f"operation {repeat} repeats the name")
    return ClData(work_offset, rebuilt)
