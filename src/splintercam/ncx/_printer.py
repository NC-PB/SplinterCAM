# SPDX-License-Identifier: Apache-2.0
"""The number printer: values as counts of the step 10^-6, rounded half away from zero from the
exact value, then as positional text (REQ-NCX-008 to 010; research 26, Number printer;
DEC-NCX-002)."""

import numpy as np
from numpy.typing import NDArray

STEPS_PER_UNIT = 1_000_000  # D-149: the fixed NCX resolution, 0.000001 mm
# REQ-NCX-010: below it every count lies below 2^50, where floor and the int64 cast are exact.
VALUE_LIMIT = 1e9
_SCALE = float(STEPS_PER_UNIT)  # 2^6 · 15625: 14 significant bits
_SPLITTER = 2.0**27 + 1.0  # Veltkamp's split into two halves of 26 bits (Dekker 1971)


def to_steps(values: NDArray[np.float64]) -> NDArray[np.int64]:
    """Each value's count of steps, half away from zero on the exact value·10^6; every value
    finite and of magnitude below `VALUE_LIMIT`, so -0 and tiny values give the count 0."""
    size = np.abs(values)
    # Dekker 1971: Veltkamp's split, then size·10^6 = product + error exactly: both halves
    # times the 14 bits of 10^6 are exact, and Fast2Sum adds them without loss.
    split = _SPLITTER * size
    high = split - (split - size)
    high_part, low_part = high * _SCALE, (size - high) * _SCALE
    product = high_part + low_part
    error = low_part - (product - high_part)
    whole = np.floor(product)
    # Exact for every product that matters: the fraction is a multiple of the product's ulp,
    # and so is 0.5; |error| is at most half that ulp, so it decides only a printed tie.
    beyond_half = (product - whole) - 0.5
    up = (beyond_half > 0.0) | ((beyond_half == 0.0) & (error >= 0.0))
    counts: NDArray[np.int64] = whole.astype(np.int64) + up.astype(np.int64)
    signed: NDArray[np.int64] = np.where(values < 0.0, -counts, counts)
    return signed


def to_text(counts: NDArray[np.int64]) -> NDArray[np.str_]:
    """The counts as NCX numbers: at least one digit on each side of the point, the fraction's
    trailing zeros trimmed, no exponent, no plus sign (research 26, trap 2)."""
    size = np.abs(counts)
    whole, fraction = size // STEPS_PER_UNIT, size % STEPS_PER_UNIT
    digits = np.strings.rstrip(np.strings.zfill(fraction.astype(np.str_), 6), "0")
    digits = np.where(digits == "", "0", digits)
    sign = np.where(counts < 0, "-", "")
    return np.strings.add(np.strings.add(sign, whole.astype(np.str_)), np.strings.add(".", digits))
