# SPDX-License-Identifier: Apache-2.0
"""An operation's moves as printed values and as NCX blocks, column by column in NumPy (split
rule; REQ-NCX-004 to 008, DEC-NCX-002, DEC-NCX-004)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from splintercam.cl import ClOperation, MoveKind

from ._printer import VALUE_LIMIT, to_steps, to_text

X, Y, Z, CENTRE_X, CENTRE_Y, FEED = range(6)  # the printed columns
_WORDS = np.array(["RAPID", "LINE", "ARC=CW", "ARC=CCW"])  # by kind, + 1 for a CCW arc


@dataclass(frozen=True, slots=True, eq=False)
class Printed:
    """One operation's values to print, (n, 6) in the column order above; NaN where none."""

    values: NDArray[np.float64]
    too_large: NDArray[np.bool_]  # (n,) a value of 10^9 or more (REQ-NCX-010)
    counts: NDArray[np.int64]  # (n, 6) steps of 10^-6; 0 where none or too large


def printed(operation: ClOperation) -> Printed:
    """The operation's columns, Z shifted by the axial offset a (D-154, REQ-NCX-007)."""
    header, moves = operation.header, operation.moves
    feeds = np.array([feed for _, feed in header.feed_classes] + [np.nan], dtype=np.float64)
    values = np.column_stack(
        (
            moves.end_mm[:, X],
            moves.end_mm[:, Y],
            moves.end_mm[:, Z] + header.axial_offset_mm,
            moves.centre_mm,
            feeds[moves.feed_class],  # NO_FEED_CLASS (-1) picks the NaN
        )
    )
    finite = np.isfinite(values)
    large = finite & (np.abs(np.where(finite, values, 0.0)) >= VALUE_LIMIT)
    counts = to_steps(np.where(finite & ~large, values, 0.0))
    return Printed(values, large.any(axis=1), counts)


def move_blocks(operation: ClOperation, columns: Printed) -> list[str]:
    """One block per move: the first as `RAPID Z=` alone (REQ-CL-006), every other with X, Y
    and Z; arcs with the centre; `F` on the first feed move and where the feed changes."""
    moves = operation.moves
    text = to_text(columns.counts)
    arc = moves.kind == MoveKind.ARC
    word = _WORDS[moves.kind + (arc & (moves.sweep_rad > 0.0))]
    blocks = word + " X=" + text[:, X] + " Y=" + text[:, Y] + " Z=" + text[:, Z]
    centre = " CENTER:X=" + text[:, CENTRE_X] + " CENTER:Y=" + text[:, CENTRE_Y]
    blocks = blocks + np.where(arc, centre, "")
    feed_moves = np.flatnonzero(moves.kind != MoveKind.RAPID)
    feeds = columns.values[feed_moves, FEED]
    changes = np.ones(len(feed_moves), dtype=np.bool_)  # the first, DEC-NCX-004
    changes[1:] = feeds[1:] != feeds[:-1]
    with_feed = np.zeros(len(blocks), dtype=np.bool_)
    with_feed[feed_moves[changes]] = True
    blocks = blocks + np.where(with_feed, " F=" + text[:, FEED], "")
    return [f"RAPID Z={text[0, Z]}", *(str(block) for block in blocks[1:])]
