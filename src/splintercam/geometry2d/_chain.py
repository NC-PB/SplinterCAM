# SPDX-License-Identifier: Apache-2.0
"""The flattened open chain of a profile (research 01, Flattening with a known error side;
D-025)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam.foundation import Context, Result

from ._flatten import AirSide
from ._loops import flattened
from ._rows import checked_rows


@dataclass(frozen=True, slots=True)
class FlatChain:
    """An open chain flattened within t_flat: `points` (n, 2), from the first row's start to the
    last row's end; `source_ids` (n - 1,), per edge the ID of its row; the extra clearance the
    flattening needs beyond t_flat. Read-only."""

    points: NDArray[np.float64]
    source_ids: NDArray[np.int64]
    extra_clearance_mm: float


def build_chain(
    rows: ArrayLike, ids: ArrayLike, air_side: AirSide, ctx: Context
) -> Result[FlatChain]:
    """One open chain of lines and arcs flattened for a profile: rows checked as `curve_rows`
    checks a loop, without its closure (`CURVE_INVALID`, `ARC_INCONSISTENT`); every arc within
    t_flat with its error on `air_side`, the side the tool works on: inscribed when its centre
    lies there (left of the arc for a positive sweep), each joint once. Lines and arcs only, so
    the extra clearance is 0.

    Implements: REQ-G2D-117, REQ-G2D-125, REQ-G2D-127, REQ-G2D-234.
    """
    checked = checked_rows(rows, ids, np.zeros(1, np.int64), ctx, closed=False)
    chain = checked.value
    if chain is None:
        return Result(None, checked.diagnostics)
    centre_left = chain.rows[:, 6] > 0.0
    flags = (centre_left == (air_side is AirSide.LEFT)).astype(np.uint8)
    open_part = flattened(
        chain, flags, ctx.tolerances.flatten_tol_mm, portable=False, min_vertices=0
    )
    points = np.vstack([open_part.points, chain.rows[-1:, 2:4]])
    points.flags.writeable = False
    return Result(FlatChain(points, open_part.source_ids, 0.0))
