# SPDX-License-Identifier: Apache-2.0
"""Cleanup of a closed polyline (research 01, Helpers)."""

import numpy as np
from numpy.typing import ArrayLike, NDArray

from splintercam import _kernels
from splintercam.foundation import Context, Diagnostic, Result, Severity

from ._predicates import point_rows


def cleanup(points: ArrayLike, ctx: Context) -> Result[NDArray[np.int64]]:
    """The indices, in order, of the vertices of a closed polyline ((n, 2)) that cleanup keeps:
    runs within eps_len merged, exactly collinear vertices and zero-width spikes dropped, one
    `CLEANUP_SPIKE` (info) per spike. A NaN or infinite point is a `ValueError`.

    Implements: REQ-G2D-020, REQ-G2D-204 to 207, REQ-G2D-209, REQ-G2D-211, REQ-G2D-212.
    """
    (rows,) = point_rows(points)
    status = np.empty(rows.shape[0], dtype=np.int8)  # 1 kept, 0 dropped, 2 dropped as a spike
    _kernels.geometry2d.cleanup_loop(rows, ctx.tolerances.length_eps_mm, status)
    kept = np.flatnonzero(status == 1).astype(np.int64)
    kept.flags.writeable = False
    diagnostics = tuple(
        Diagnostic("CLEANUP_SPIKE", Severity.INFO, "zero-width spike dropped", f"vertex {i}")
        for i in np.flatnonzero(status == 2).tolist()
    )
    return Result(kept, diagnostics)
