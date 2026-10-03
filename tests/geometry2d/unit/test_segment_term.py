# SPDX-License-Identifier: Apache-2.0
"""Unit tests for phi - sin(phi) from basic operations, the circular segment term of the signed area
(research 01, Area and orientation; REQ-G2D-018: the same bits on every platform)."""

import math
from fractions import Fraction

import numpy as np
import pytest

from splintercam import _kernels

U = 2.0**-53


def _kernel(phi: list[float]) -> list[float]:
    out = np.empty(len(phi))
    _kernels.geometry2d.phi_minus_sin(np.array(phi), out)
    return [float(v) for v in out]


def _exact(phi: float) -> Fraction:
    # φ³/3! - φ⁵/5! + …: 40 terms leave less than (2π)^83 / 83! < 1e-58 for |φ| <= 2π.
    x, total, term = Fraction(phi), Fraction(0), Fraction(phi)
    for k in range(1, 41):
        term = term * x * x / ((2 * k) * (2 * k + 1))
        total += term if k % 2 == 1 else -term
    return total


PHIS = [
    *(math.copysign(2.0**-e, s) for e in (1, 10, 30, 60) for s in (1, -1)),
    *np.linspace(-math.tau, math.tau, 101).tolist(),
    1.0,
    1.0 + 2.0**-52,
    math.pi,
    -math.pi,
]


@pytest.mark.req("REQ-G2D-128")
def test_within_a_few_rounding_units_of_the_exact_series() -> None:
    for phi, got in zip(PHIS, _kernel(PHIS), strict=True):
        exact = _exact(phi)
        # Relative near 0, where the series has no cancellation; absolute in φ beyond |φ| = 1.
        scale = max(abs(float(exact)), 1.0 if abs(phi) > 1.0 else 0.0)
        assert abs(Fraction(got) - exact) <= Fraction(16 * U * scale), phi


@pytest.mark.req("REQ-G2D-128")
def test_odd_and_exact_at_the_full_turn() -> None:
    phis = [0.3, 2.0, 5.0, math.tau]
    assert _kernel([-p for p in phis]) == [-v for v in _kernel(phis)]
    assert _kernel([0.0]) == [0.0]
    assert _kernel([math.tau])[0] == pytest.approx(math.tau, abs=4 * U * math.tau)


# Computed on Linux x86-64 when the function was written: every platform must give these bits.
PINNED: list[tuple[float, str]] = [
    (0.001, "0x1.6e80fccfca714p-33"),
    (0.5, "0x1.51178bb4fa103p-6"),
    (1.5, "0x1.0148564d39274p-1"),
    (3.0, "0x1.6defc792492aap+1"),
    (-6.0, "-0x1.91e1f18ab0a2cp+2"),
]


@pytest.mark.req("REQ-G2D-018")
def test_the_same_bits_on_every_platform() -> None:
    phis = [row[0] for row in PINNED]
    assert [float.hex(v) for v in _kernel(phis)] == [row[1] for row in PINNED]
