# SPDX-License-Identifier: Apache-2.0
"""The tolerance defaults file and its declared parameters (REQ-FND-008, D-049)."""

import tomllib
import types
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_DEFAULTS_FILE = Path(__file__).with_name("tolerance_defaults.toml")
_KEYS = frozenset({"default", "unit", "range", "source"})


@dataclass(frozen=True, slots=True)
class DeclaredParameter:
    """One value of the tolerance defaults file, with its unit, range and source (D-049).

    Attributes:
        default: the value, in `unit`.
        unit: the unit of `default` and `range`, for example "mm", "rad" or "share of tol".
        range: the smallest and the largest allowed value, inclusive; both are the default for
            a fixed value.
        source: the decision or research section the value comes from.

    Implements: REQ-FND-008.
    """

    default: float
    unit: str
    range: tuple[float, float]
    source: str


def _parameter(name: str, entry: dict[str, Any]) -> DeclaredParameter:
    where = f"{_DEFAULTS_FILE.name}, {name}"
    if frozenset(entry) != _KEYS:
        raise ValueError(f"{where}: needs exactly the keys {sorted(_KEYS)}")
    low, high = (float(bound) for bound in entry["range"])
    parameter = DeclaredParameter(
        float(entry["default"]), str(entry["unit"]), (low, high), str(entry["source"])
    )
    if not (low <= parameter.default <= high and parameter.unit and parameter.source):
        raise ValueError(f"{where}: default outside its range, or no unit or source")
    return parameter


def _read_defaults() -> Mapping[str, DeclaredParameter]:
    with _DEFAULTS_FILE.open("rb") as file:
        table = tomllib.load(file)
    return types.MappingProxyType({name: _parameter(name, entry) for name, entry in table.items()})


TOLERANCE_DEFAULTS = _read_defaults()
"""Every entry of `tolerance_defaults.toml`, by name, read once at import (REQ-FND-008).

For building tolerance sets and declaring parameters; a computation reads its tolerances from its
`Context` (REQ-FND-005).
"""
