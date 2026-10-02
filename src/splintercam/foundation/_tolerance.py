# SPDX-License-Identifier: Apache-2.0
"""The tolerance budget (ToleranceSet) and the nearly_equal comparison helper."""

import fractions
import math
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal

from ._defaults import TOLERANCE_DEFAULTS
from ._result import Diagnostic, Result, Severity

BUDGET_PARTS: tuple[str, ...] = ("geometry", "fit", "control", "reserve")
"""The parts of the operation tolerance, in the order `ToleranceSet.stage_shares` keeps (D-056)."""


def _default(name: str) -> float:
    return TOLERANCE_DEFAULTS[name].default


# The numbers of REQ-FND-009, all from the defaults file (research 01, Tolerances).
_DEFAULT_SHARES = tuple((part, _default(f"share_{part}")) for part in BUDGET_PARTS)
_GRID_UNIT_MM = _default("grid_unit_mm")
_ROUNDING_MARGIN_MM = _default("rounding_margin_grid_units") * _GRID_UNIT_MM  # D-132
_ARC_TOL_SHARE = _default("arc_tol_share")  # a = max(0.05·tol, 2u), D-058
_ARC_TOL_FLOOR_MM = _default("arc_tol_floor_grid_units") * _GRID_UNIT_MM
_IMPORT_ARC_DEVIATION_MM = _default("import_arc_deviation_mm")  # D-093
_SNAP_ALLOWANCE_LENGTH_EPS = _default("snap_allowance_length_eps")
_TOPOLOGY_TOL_MM = _default("topology_tol_grid_units") * _GRID_UNIT_MM
# The fit band, (0.3 + 0.05)·tol - (6 + 2)·u below tol = 2u/0.05, is 0 at tol_min = 8u/0.35;
# computed once, in double, it is the double nearest 2/875 mm (research 01, Tolerances).
_TOL_MIN_MM = (
    (_default("rounding_margin_grid_units") + _default("arc_tol_floor_grid_units"))
    * _GRID_UNIT_MM
    / (_default("share_fit") + _ARC_TOL_SHARE)
)
# Rounded up, so that the value a refusal suggests is accepted.
_TOL_MIN_NAMED = str(
    Decimal(_TOL_MIN_MM).quantize(
        Decimal(repr(_default("tol_min_step_mm"))), rounding=ROUND_CEILING
    )
)


def _require_positive_finite(field_name: str, value: float) -> None:
    """Raise `ValueError` naming `field_name` unless `value` is finite and strictly positive."""
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{field_name} must be finite and > 0, got {value!r}")


@dataclass(frozen=True, slots=True)
class ToleranceSet:
    """The tolerance budget of one operation (research 01, "Tolerances"; D-056, D-146, D-149).

    All lengths are in millimetres, all angles in radians (docs/dev/04, "Units").

    Attributes:
        chord_tol_mm: tol, the largest deviation of the finished wall from the model, the control
            included (D-056).
        length_eps_mm: two points closer than this, in mm, are the same point.
        angle_eps_rad: two directions closer than this, in radians, are parallel.
        stage_shares: (part, share) for each of `BUDGET_PARTS`: its base share of tol. Stored in
            `BUDGET_PARTS` order whatever the input order, so equal sets compare and hash equal.

    Preconditions (REQ-FND-002), checked in `__post_init__` and reported as `ValueError`:
    the three tolerances are finite and > 0; `stage_shares` names each budget part exactly once;
    each share is finite and >= 0; the shares sum to at most 1, compared exactly as fractions,
    since this check defines the budget that tolerances are drawn from.

    Build an operation's set with `for_operation`, which takes the defaults (REQ-FND-008).

    Implements: REQ-FND-001, REQ-FND-002, REQ-FND-007, REQ-FND-009.
    """

    chord_tol_mm: float
    length_eps_mm: float
    angle_eps_rad: float
    stage_shares: tuple[tuple[str, float], ...]

    def __post_init__(self) -> None:
        _require_positive_finite("chord_tol_mm", self.chord_tol_mm)
        _require_positive_finite("length_eps_mm", self.length_eps_mm)
        _require_positive_finite("angle_eps_rad", self.angle_eps_rad)

        shares = dict(self.stage_shares)
        if len(shares) != len(self.stage_shares) or set(shares) != set(BUDGET_PARTS):
            message = f"stage_shares must name each of {BUDGET_PARTS} once, got {self.stage_shares}"
            raise ValueError(message)
        for part, share in shares.items():
            if not math.isfinite(share) or share < 0.0:
                raise ValueError(f"stage_shares[{part!r}] must be finite and >= 0, got {share!r}")
        # Exact fractions: a float sum, even math.fsum, can round a total just over 1 down to 1.
        total = sum((fractions.Fraction(share) for share in shares.values()), fractions.Fraction(0))
        if total > 1:
            raise ValueError(f"stage_shares must sum to at most 1, got {float(total)!r}")
        # Frozen dataclass: __setattr__ is disabled outside __init__/__post_init__.
        object.__setattr__(self, "stage_shares", tuple((p, shares[p]) for p in BUDGET_PARTS))

    def stage_tol_mm(self, stage: str) -> float:
        """The budget part `stage` of tol, in mm (REQ-FND-009).

        Control and reserve are their share of tol. Geometry is its share plus what the offset
        kernel's grid costs: its rounding margin of 6 grid units (D-132) and max(0, 2u - 0.05·tol)
        for the floor of its arc tolerance (D-058); the fit band is its share minus that cost,
        clamped at 0 (D-146). Evaluated in double in the order of the formulas.

        `stage` must be one of `BUDGET_PARTS`; any other is a programming error, `ValueError`.
        """
        shares = dict(self.stage_shares)
        if stage not in shares:
            raise ValueError(f"unknown stage {stage!r}")
        part = shares[stage] * self.chord_tol_mm
        arc_floor_cost = max(0.0, _ARC_TOL_FLOOR_MM - _ARC_TOL_SHARE * self.chord_tol_mm)
        if stage == "geometry":
            return part + _ROUNDING_MARGIN_MM + arc_floor_cost
        if stage == "fit":
            return max(0.0, part - _ROUNDING_MARGIN_MM - arc_floor_cost)
        return part

    @property
    def flatten_tol_mm(self) -> float:
        """t_flat in mm: what geometry leaves for flattening besides the offset's arc tolerance,
        arcs recognised at import and snapping, (0.1 - 0.05)·tol - 0.0001 mm - 3·eps_len
        (REQ-FND-009; research 01, Tolerances). Positive for every tol from tol_min up."""
        flatten_share = dict(self.stage_shares)["geometry"] - _ARC_TOL_SHARE
        return (
            flatten_share * self.chord_tol_mm
            - _IMPORT_ARC_DEVIATION_MM
            - _SNAP_ALLOWANCE_LENGTH_EPS * self.length_eps_mm
        )

    @property
    def topology_tol_mm(self) -> float:
        """t_topo = 2u in mm: features closer than this count as touching in the float stages
        (REQ-FND-009; research 01, resolution chain)."""
        return _TOPOLOGY_TOL_MM

    @classmethod
    def for_operation(cls, tol_mm: float) -> Result["ToleranceSet"]:
        """The tolerance set of an operation with tolerance `tol_mm`, with the defaults of
        REQ-FND-008 for the epsilons and the shares (REQ-FND-009).

        Below tol_min = 8u/0.35 = 2/875 mm the fit band would be negative: the result has no
        value and the error `TOL_BELOW_MINIMUM`, whose message names tol_min rounded up to
        0.1 nm, 0.0022858 mm (D-146, D-149). A non-finite `tol_mm` is a programming error,
        `ValueError`. Takes no `Context`: the `Context` holds the set this builds.
        """
        if not math.isfinite(tol_mm):
            raise ValueError(f"tol_mm must be finite, got {tol_mm!r}")
        if tol_mm < _TOL_MIN_MM:
            message = (
                f"tolerance {tol_mm!r} mm is below the smallest supported tolerance; "
                f"use at least {_TOL_MIN_NAMED} mm"
            )
            return Result(None, (Diagnostic("TOL_BELOW_MINIMUM", Severity.ERROR, message),))
        tolerances = cls(
            chord_tol_mm=tol_mm,
            length_eps_mm=_default("length_eps_mm"),
            angle_eps_rad=_default("angle_eps_rad"),
            stage_shares=_DEFAULT_SHARES,
        )
        return Result(tolerances)


def nearly_equal(a: float, b: float, tol: float) -> bool:
    """True exactly when |a - b| <= tol, evaluated in double (IEEE binary64) precision.

    `a`, `b` and `tol` are in the same unit (mm or rad, docs/dev/04 "Units"); `tol` is expected
    to be >= 0, though this is not checked: a negative `tol` always gives False, since no
    absolute difference can be <= a negative number.

    False whenever `a`, `b` or `tol` is NaN, because every comparison with NaN is false. For
    infinite inputs the same expression applies with no special case: `nearly_equal(inf, inf,
    1.0)` is False because `inf - inf` is NaN (REQ-FND-003, Peter's answer of 2026-09-27).

    Accepts NumPy scalars (for example `np.float64`) as well as Python floats and always
    returns a Python `bool`, never a NumPy scalar: use this, not `math.isclose` or
    `np.isclose`, which add a relative tolerance component and treat equal infinities as
    close, both wrong for a fixed geometric tolerance budget.

    Implements: REQ-FND-003.
    """
    return bool(abs(float(a) - float(b)) <= float(tol))
