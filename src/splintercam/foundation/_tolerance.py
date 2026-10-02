# SPDX-License-Identifier: Apache-2.0
"""The tolerance budget (ToleranceSet) and the nearly_equal comparison helper."""

import fractions
import math
import types
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _require_positive_finite(field_name: str, value: float) -> None:
    """Raise `ValueError` naming `field_name` unless `value` is finite and strictly positive."""
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{field_name} must be finite and > 0, got {value!r}")


@dataclass(frozen=True, slots=True)
class ToleranceSet:
    """The tolerance budget for one computation (RESEARCH 01, "Tolerances").

    All lengths are in millimetres, all angles in radians (docs/dev/04, "Units").

    Attributes:
        length_eps_mm: two points closer than this, in mm, are the same point.
        angle_eps_rad: two directions closer than this, in radians, are parallel.
        chord_tol_mm: the maximum allowed deviation, in mm, of a flattened path from the
            true geometry.
        stage_shares: for each named stage (for example "offset", "fitting"), its share of
            `chord_tol_mm`. Stored as an immutable copy: mutating the mapping passed in does
            not change this `ToleranceSet`, and the stored mapping itself cannot be written to.

    Preconditions (REQ-FND-002), checked in `__post_init__` and reported as `ValueError`
    naming the offending field: `length_eps_mm`, `angle_eps_rad` and `chord_tol_mm` are each
    finite and > 0; each share is finite and >= 0; the shares sum to at most 1 (compared
    exactly, with no tolerance of its own, since this check defines the budget that tolerances
    are drawn from).

    Invariant: immutable and hashable, like every foundation value type (SPEC "Invariants").

    Implements: REQ-FND-001, REQ-FND-002.
    """

    length_eps_mm: float
    angle_eps_rad: float
    chord_tol_mm: float
    stage_shares: Mapping[str, float]

    def __post_init__(self) -> None:
        _require_positive_finite("length_eps_mm", self.length_eps_mm)
        _require_positive_finite("angle_eps_rad", self.angle_eps_rad)
        _require_positive_finite("chord_tol_mm", self.chord_tol_mm)

        shares = dict(self.stage_shares)
        for name, share in shares.items():
            if not math.isfinite(share) or share < 0.0:
                raise ValueError(f"stage_shares[{name!r}] must be finite and >= 0, got {share!r}")
        # Summed as exact Fractions, not float or math.fsum: this check defines the budget
        # tolerances are drawn from, so it must not accept a sum that is actually over 1 just
        # because IEEE rounding brought it back down (math.fsum rounds {1.0, 1e-17} to 1.0 and
        # would wrongly accept it). Fraction sums are exact and so, unlike a running float sum,
        # order-independent too.
        total = sum((fractions.Fraction(share) for share in shares.values()), fractions.Fraction(0))
        if total > 1:
            raise ValueError(f"stage_shares must sum to at most 1, got {float(total)!r}")

        # Frozen dataclass: __setattr__ is disabled outside __init__/__post_init__, so a
        # defensive, read-only copy replaces whatever mapping the caller passed in.
        object.__setattr__(self, "stage_shares", types.MappingProxyType(shares))

    def stage_tol_mm(self, stage: str) -> float:
        """The tolerance budget for `stage`, in millimetres: `chord_tol_mm * stage_shares[stage]`.

        `stage` must be a key of `stage_shares`; an unknown stage is a programming error and
        raises `ValueError`. Implements REQ-FND-001.
        """
        if stage not in self.stage_shares:
            raise ValueError(f"unknown stage {stage!r}")
        return self.chord_tol_mm * self.stage_shares[stage]

    def __reduce__(self) -> tuple[type["ToleranceSet"], tuple[Any, ...]]:
        # The dataclass-generated pickling would pickle stage_shares directly, and a
        # MappingProxyType is not picklable (like the dict it wraps might not always be safe to
        # share), so __reduce__ rebuilds the set from its four fields instead. `copy.deepcopy`
        # uses the same protocol, so this also makes deep copies work (RESEARCH 18, "general
        # engineering": failure dumps and worker processes need to pickle their inputs).
        return (
            ToleranceSet,
            (
                self.length_eps_mm,
                self.angle_eps_rad,
                self.chord_tol_mm,
                dict(self.stage_shares),
            ),
        )

    def __hash__(self) -> int:
        # The dataclass-generated __hash__ would hash stage_shares directly, and a
        # MappingProxyType (like the dict it wraps) is not hashable, so it is unpacked here.
        return hash(
            (
                self.length_eps_mm,
                self.angle_eps_rad,
                self.chord_tol_mm,
                tuple(sorted(self.stage_shares.items())),
            )
        )


def nearly_equal(a: float, b: float, tol: float) -> bool:
    """True exactly when |a - b| <= tol, evaluated in double (IEEE binary64) precision.

    `a`, `b` and `tol` are in the same unit (mm or rad, docs/dev/04 "Units"); `tol` is expected
    to be >= 0, though this is not checked: a negative `tol` always gives False, since no
    absolute difference can be <= a negative number.

    False whenever `a`, `b` or `tol` is NaN, because every comparison with NaN is false. For
    infinite inputs the same expression applies with no special case: `nearly_equal(inf, inf,
    1.0)` is False because `inf - inf` is NaN (SPEC "Open questions": confirm with Peter).

    Accepts NumPy scalars (for example `np.float64`) as well as Python floats and always
    returns a Python `bool`, never a NumPy scalar: use this, not `math.isclose` or
    `np.isclose`, which add a relative tolerance component and treat equal infinities as
    close, both wrong for a fixed geometric tolerance budget.

    Implements: REQ-FND-003.
    """
    return bool(abs(float(a) - float(b)) <= float(tol))
