# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the Context dataclass: all six fields, and frozen (REQ-FND-005)."""

import dataclasses
import logging

import pytest

from splintercam.foundation import CancellationToken, Context, ToleranceSet


@pytest.mark.req("REQ-FND-005")
def test_context_carries_all_six_fields(ctx: Context) -> None:
    assert isinstance(ctx.tolerances, ToleranceSet)
    assert isinstance(ctx.cancel, CancellationToken)
    assert callable(ctx.progress)
    assert isinstance(ctx.logger, logging.Logger)
    assert hasattr(ctx.debug, "add")
    assert isinstance(ctx.seed, int)


@pytest.mark.req("REQ-FND-005")
def test_context_has_exactly_the_six_specified_fields() -> None:
    assert [f.name for f in dataclasses.fields(Context)] == [
        "tolerances",
        "cancel",
        "progress",
        "logger",
        "debug",
        "seed",
    ]


@pytest.mark.req("REQ-FND-005")
def test_context_stores_the_exact_objects_passed_in() -> None:
    # Finishing tol, eps_len, eps_ang and D-056's shares (research 01, Tolerances).
    tolerances = ToleranceSet(
        chord_tol_mm=0.01,
        length_eps_mm=1e-6,
        angle_eps_rad=1e-9,
        stage_shares=(("geometry", 0.1), ("fit", 0.3), ("control", 0.5), ("reserve", 0.1)),
    )
    cancel = CancellationToken()
    logger = logging.getLogger("splintercam.tests.identity")

    def progress(_fraction: float) -> None:
        return None

    class _Sink:
        def add(self, name: str, kind: str, data: object) -> None:
            del name, kind, data
            return None

    debug = _Sink()
    context = Context(
        tolerances=tolerances,
        cancel=cancel,
        progress=progress,
        logger=logger,
        debug=debug,
        seed=7,
    )
    assert context.tolerances is tolerances
    assert context.cancel is cancel
    assert context.progress is progress
    assert context.logger is logger
    assert context.debug is debug
    assert context.seed == 7


@pytest.mark.req("REQ-FND-007")
def test_context_is_frozen(ctx: Context) -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.seed = 1  # pyright: ignore[reportAttributeAccessIssue]
