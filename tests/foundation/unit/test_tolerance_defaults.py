# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the tolerance defaults file and TOLERANCE_DEFAULTS (REQ-FND-008)."""

import tomllib
from pathlib import Path
from typing import Any

import pytest

import splintercam.foundation as foundation
from splintercam.foundation import BUDGET_PARTS, TOLERANCE_DEFAULTS, ToleranceSet

# The documented defaults file next to the code (foundation SPEC, Tolerance budget).
_DEFAULTS_FILE = Path(foundation.__file__).with_name("tolerance_defaults.toml")

# Decimal defaults are compared with ==: tomllib and the Python parser both round a decimal
# literal to the nearest double, so the same decimal gives the same double.


def _read_defaults_file() -> dict[str, dict[str, Any]]:
    """The entries of the defaults file, read independently of foundation: its top-level tables."""
    with _DEFAULTS_FILE.open("rb") as file:
        document = tomllib.load(file)
    return {name: entry for name, entry in document.items() if isinstance(entry, dict)}


@pytest.mark.req("REQ-FND-008")
def test_defaults_file_has_the_same_entries_as_tolerance_defaults() -> None:
    entries = _read_defaults_file()
    assert sorted(entries) == sorted(TOLERANCE_DEFAULTS)
    for name, entry in entries.items():
        parameter = TOLERANCE_DEFAULTS[name]
        assert parameter.default == entry["default"], name
        assert parameter.unit == entry["unit"], name
        assert parameter.range == tuple(entry["range"]), name
        assert parameter.source == entry["source"], name


@pytest.mark.req("REQ-FND-008")
def test_every_default_has_unit_and_source_and_lies_in_its_inclusive_range() -> None:
    assert TOLERANCE_DEFAULTS
    for name, parameter in TOLERANCE_DEFAULTS.items():
        assert parameter.unit.strip(), name
        assert parameter.source.strip(), name
        low, high = parameter.range
        assert low <= parameter.default <= high, name


@pytest.mark.req("REQ-FND-008")
@pytest.mark.parametrize(
    ("name", "default", "unit"),
    [
        ("chord_tol_roughing_mm", 0.05, "mm"),  # D-029
        ("chord_tol_finishing_mm", 0.01, "mm"),  # D-029
        ("length_eps_mm", 1e-6, "mm"),  # Q-034 answer
        ("angle_eps_rad", 1e-9, "rad"),  # Q-034 answer
        ("share_geometry", 0.1, None),  # D-056
        ("share_fit", 0.3, None),
        ("share_control", 0.5, None),
        ("share_reserve", 0.1, None),
    ],
)
def test_decided_defaults_with_their_units(name: str, default: float, unit: str | None) -> None:
    parameter = TOLERANCE_DEFAULTS[name]
    assert parameter.default == default
    if unit is not None:
        assert parameter.unit == unit


@pytest.mark.req("REQ-FND-008")
def test_for_operation_takes_epsilons_and_shares_from_the_defaults() -> None:
    budget = ToleranceSet.for_operation(0.01).value
    assert budget is not None
    assert budget.length_eps_mm == TOLERANCE_DEFAULTS["length_eps_mm"].default
    assert budget.angle_eps_rad == TOLERANCE_DEFAULTS["angle_eps_rad"].default
    expected_shares = tuple(
        (part, TOLERANCE_DEFAULTS[f"share_{part}"].default) for part in BUDGET_PARTS
    )
    assert budget.stage_shares == expected_shares
