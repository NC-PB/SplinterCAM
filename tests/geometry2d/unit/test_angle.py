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


# The angle REQ-G2D-043 decides with: exact on the axes, accurate elsewhere.
@pytest.mark.req("REQ-G2D-043", "REQ-G2D-233")
def test_axis_directions_and_the_origin() -> None:
    angles = _basic_atan2([0.0, 1.0, 0.0, -1.0, 0.0], [1.0, 0.0, -1.0, 0.0, 0.0])
    assert angles == [0.0, math.pi / 2, math.pi, -math.pi / 2, 0.0]


# (y, x, angle) as hex: pinned on Linux, so CI on macOS and Windows shows the same bits (D-055,
# tier 1). The inputs sit at and beside the branch points tan(pi/12) = 2 - sqrt(3), 1/sqrt(3) and
# 1, at extreme ratios, and on the negative x axis with +0.0 and -0.0.
PINNED = [
    ("0x1.126145e9ecd58p-2", "0x1.0000000000000p+0", "0x1.0c152382d7367p-2"),
    ("0x1.126145e9ecd59p-2", "0x1.0000000000000p+0", "0x1.0c152382d7366p-2"),
    ("0x1.279a74590331dp-1", "0x1.0000000000000p+0", "0x1.0c152382d7365p-1"),
    ("0x1.0000000000000p+0", "0x1.0000000000000p+0", "0x1.921fb54442d18p-1"),
    ("0x1.0000000000001p+0", "0x1.0000000000000p+0", "0x1.921fb54442d19p-1"),
    ("0x1.fffffffffffffp-1", "0x1.0000000000000p+0", "0x1.921fb54442d17p-1"),
    ("0x1.7e43c8800759cp+996", "0x1.56e1fc2f8f359p-997", "0x1.921fb54442d18p+0"),
    ("0x1.56e1fc2f8f359p-997", "0x1.0000000000000p+0", "0x1.56e1fc2f8f359p-997"),
    ("0x0.0p+0", "-0x1.0000000000000p+0", "0x1.921fb54442d18p+1"),
    ("-0x0.0p+0", "-0x1.0000000000000p+0", "0x1.921fb54442d18p+1"),
    ("-0x1.0000000000000p+0", "-0x1.0000000000000p+0", "-0x1.2d97c7f3321d2p+1"),
    ("0x1.8000000000000p+1", "-0x1.0000000000000p+2", "0x1.3fc176b7a8560p+1"),
    ("-0x1.4000000000000p+2", "0x1.8000000000000p+3", "-0x1.94441f8f7260ap-2"),
]


@pytest.mark.req("REQ-G2D-018", "REQ-G2D-233")
def test_the_same_bits_on_every_platform() -> None:
    y = [float.fromhex(row[0]) for row in PINNED]
    x = [float.fromhex(row[1]) for row in PINNED]
    assert [float.hex(angle) for angle in _basic_atan2(y, x)] == [row[2] for row in PINNED]


@pytest.mark.req("REQ-G2D-043", "REQ-G2D-233")
def test_within_four_rounding_units_of_libm_over_all_directions() -> None:
    # The reference is the platform's atan2, itself within a rounding unit or so of the truth.
    rng = np.random.default_rng(1)
    angles = rng.uniform(-math.pi, math.pi, 20_000)
    lengths = 10.0 ** rng.uniform(-6.0, 4.0, angles.size)
    y, x = (lengths * np.sin(angles)).tolist(), (lengths * np.cos(angles)).tolist()
    for got, (yi, xi) in zip(_basic_atan2(y, x), zip(y, x, strict=True), strict=True):
        expected = math.atan2(yi, xi)
        assert abs(got - expected) <= 4 * math.ulp(max(abs(expected), 1e-300)), (yi, xi)
