# SPDX-License-Identifier: Apache-2.0
"""Drawing units: the `$INSUNITS` codes io reads and the conversion to millimetres (D-028, D-033,
DEC-IO-002; research 21, Method 2). Every coordinate is scaled once, at import; sweeps are not."""

from enum import Enum

# The `$INSUNITS` values io reads, and their factor to millimetres (REQ-IO-004).
_INSUNITS_TO_MM: dict[int, float] = {4: 1.0, 1: 25.4, 5: 10.0, 6: 1000.0}

# Names of the `$INSUNITS` values DXF defines, for the `DXF_UNIT_UNSUPPORTED` message (REQ-IO-005).
_INSUNITS_NAMES: dict[int, str] = {
    1: "inches", 2: "feet", 3: "miles", 4: "millimetres", 5: "centimetres", 6: "metres",
    7: "kilometres", 8: "microinches", 9: "mils", 10: "yards", 11: "angstroms", 12: "nanometres",
    13: "microns", 14: "decimetres", 15: "decametres", 16: "hectometres", 17: "gigametres",
    18: "astronomical units", 19: "light years", 20: "parsecs",
}  # fmt: skip


class DrawingUnit(Enum):
    """The unit a job may state for a DXF file without `$INSUNITS` (D-033)."""

    MILLIMETRE = 1.0
    INCH = 25.4

    @property
    def factor_mm(self) -> float:
        """The factor from this unit to millimetres."""
        return float(self.value)


def insunits_name(value: int) -> str:
    """The name DXF gives `$INSUNITS` = `value`, or a bare mention of the code (REQ-IO-005)."""
    name = _INSUNITS_NAMES.get(value)
    return f"{value} ({name})" if name is not None else f"{value} (no DXF unit name)"


def file_factor_mm(insunits: int) -> float | None:
    """The millimetre factor of a file's `$INSUNITS`, or None when io reads no unit from it
    (0 or missing, REQ-IO-005). A value io does not support raises KeyError via the caller's
    membership test; call `is_supported` first."""
    return _INSUNITS_TO_MM.get(insunits)


def is_supported(insunits: int) -> bool:
    """True for a `$INSUNITS` io reads (4, 1, 5, 6) or "no unit" (0); False for feet and the
    rest, which stop the import with `DXF_UNIT_UNSUPPORTED` (REQ-IO-005, DEC-IO-002)."""
    return insunits == 0 or insunits in _INSUNITS_TO_MM
