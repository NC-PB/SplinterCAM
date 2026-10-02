# SPDX-License-Identifier: Apache-2.0
"""Shared helpers for the geometry2d tests: contexts with other epsilons, diagnostic codes."""

import dataclasses

from splintercam.foundation import Context, Result, ToleranceSet


def with_length_eps(ctx: Context, length_eps_mm: float) -> Context:
    """`ctx` with its length epsilon replaced, the rest of its tolerance set kept."""
    tolerances = ctx.tolerances
    changed = ToleranceSet(
        chord_tol_mm=tolerances.chord_tol_mm,
        length_eps_mm=length_eps_mm,
        angle_eps_rad=tolerances.angle_eps_rad,
        stage_shares=tolerances.stage_shares,
    )
    return dataclasses.replace(ctx, tolerances=changed)


def codes[T](result: Result[T]) -> list[str]:
    """The diagnostic codes of `result`, in order."""
    return [diagnostic.code for diagnostic in result.diagnostics]
