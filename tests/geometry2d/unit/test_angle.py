# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the kernel's arctangent from IEEE basic operations (SPEC, determinism note)."""

import math

import numpy as np
import pytest

from splintercam import _kernels


def _basic_atan2(y: list[float], x: list[float]) -> list[float]:
    out = np.empty(len(y))
    _kernels.geometry2d.basic_atan2(np.array(y), np.array(x), out)
    return out.tolist()


@pytest.mark.req("REQ-G2D-018")
def test_axis_directions_and_the_origin() -> None:
    angles = _basic_atan2([0.0, 1.0, 0.0, -1.0, 0.0], [1.0, 0.0, -1.0, 0.0, 0.0])
    assert angles == [0.0, math.pi / 2, math.pi, -math.pi / 2, 0.0]


@pytest.mark.req("REQ-G2D-018")
def test_within_four_rounding_units_of_libm_over_all_directions() -> None:
    # The reference is the platform's atan2, itself within a rounding unit or so of the truth.
    rng = np.random.default_rng(1)
    angles = rng.uniform(-math.pi, math.pi, 20_000)
    lengths = 10.0 ** rng.uniform(-6.0, 4.0, angles.size)
    y, x = (lengths * np.sin(angles)).tolist(), (lengths * np.cos(angles)).tolist()
    for got, (yi, xi) in zip(_basic_atan2(y, x), zip(y, x, strict=True), strict=True):
        expected = math.atan2(yi, xi)
        assert abs(got - expected) <= 4 * math.ulp(max(abs(expected), 1e-300)), (yi, xi)
