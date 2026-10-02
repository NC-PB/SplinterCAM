# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the tolerance defaults file and TOLERANCE_DEFAULTS (REQ-FND-008)."""

import tomllib
from pathlib import Path
from typing import Any

import pytest

import splintercam.foundation as foundation
from splintercam.foundation import TOLERANCE_DEFAULTS, ToleranceSet

# The documented defaults file next to the code (foundation SPEC, Tolerance budget).
_DEFAULTS_FILE = Path(foundation.__file__).with_name("tolerance_defaults.toml")
_ENTRY_KEYS = {"default", "unit", "range", "source"}

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
        assert set(entry) >= _ENTRY_KEYS, name
        parameter = TOLERANCE_DEFAULTS[name]
        assert parameter.default == entry["default"], name
        assert parameter.unit == entry["unit"], name
        assert isinstance(parameter.range, tuple), name
        assert parameter.range == tuple(entry["range"]), name
        assert parameter.source == entry["source"], name


@pytest.mark.req("REQ-FND-008")
def test_every_default_has_unit_and_source_and_lies_in_its_inclusive_range() -> None:
    assert TOLERANCE_DEFAULTS
    for name, parameter in TOLERANCE_DEFAULTS.items():
        assert isinstance(parameter.unit, str), name
        assert parameter.unit.strip(), name
        assert isinstance(parameter.source, str), name
        assert parameter.source.strip(), name
        assert len(parameter.range) == 2, name
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
    ],
)
def test_decided_tolerance_defaults_with_their_units(name: str, default: float, unit: str) -> None:
    parameter = TOLERANCE_DEFAULTS[name]
    assert parameter.default == default
    assert parameter.unit == unit


@pytest.mark.req("REQ-FND-008")
@pytest.mark.parametrize(
    ("name", "default"),
    [
        ("share_geometry", 0.1),  # D-056
        ("share_fit", 0.3),
        ("share_control", 0.5),
        ("share_reserve", 0.1),
    ],
)
def test_decided_budget_share_defaults(name: str, default: float) -> None:
    assert TOLERANCE_DEFAULTS[name].default == default


@pytest.mark.req("REQ-FND-008")
@pytest.mark.parametrize(
    ("name", "default"),
    [
        ("grid_unit_mm", 0.0001),  # u, D-058, D-132
        ("rounding_margin_grid_units", 6),  # D-132
        ("arc_tol_share", 0.05),  # D-058
        ("arc_tol_floor_grid_units", 2),  # D-058
        ("import_arc_deviation_mm", 0.0001),  # D-093
        ("snap_allowance_length_eps", 3),  # research 01, Tolerances
        ("topology_tol_grid_units", 2),  # research 01, resolution chain
        ("tol_min_step_mm", 1e-7),  # 0.1 nm, D-146, D-149
    ],
)
def test_budget_entries_of_req_fnd_009_have_the_values_the_spec_names(
    name: str, default: float
) -> None:
    parameter = TOLERANCE_DEFAULTS[name]
    assert parameter.default == default
    # docs/dev/04: a name suffix carries the unit.
    if name.endswith("_mm"):
        assert parameter.unit == "mm"


@pytest.mark.req("REQ-FND-008")
@pytest.mark.parametrize("name", ["chord_tol_roughing_mm", "chord_tol_finishing_mm"])
def test_chord_tolerance_range_starts_at_tol_min_named_0_0022858_mm(name: str) -> None:
    low, _ = TOLERANCE_DEFAULTS[name].range
    assert low == 0.0022858


@pytest.mark.req("REQ-FND-008")
@pytest.mark.parametrize("name", ["chord_tol_roughing_mm", "chord_tol_finishing_mm"])
def test_chord_tolerance_range_ends_at_1_mm(name: str) -> None:
    # Research 01, Parameters: tol from tol_min to 1.0 mm; the SPEC's open questions say the
    # defaults file records that range.
    _, high = TOLERANCE_DEFAULTS[name].range
    assert high == 1.0


@pytest.mark.req("REQ-FND-008")
@pytest.mark.parametrize(
    "name",
    [
        "length_eps_mm",
        "angle_eps_rad",
        "grid_unit_mm",
        "import_arc_deviation_mm",
        "topology_tol_grid_units",
    ],
)
def test_fixed_values_have_their_default_at_both_ends_of_the_range(name: str) -> None:
    # Research 01, Parameters, marks these fixed; the SPEC: a fixed value has its default at both
    # ends of its range.
    parameter = TOLERANCE_DEFAULTS[name]
    assert parameter.range == (parameter.default, parameter.default)


@pytest.mark.req("REQ-FND-008")
@pytest.mark.parametrize("tol_mm", [0.0022858, 0.01, 0.05, 1.0])
def test_for_operation_takes_epsilons_and_shares_from_the_defaults(tol_mm: float) -> None:
    budget = ToleranceSet.for_operation(tol_mm).value
    assert budget is not None
    assert budget.length_eps_mm == TOLERANCE_DEFAULTS["length_eps_mm"].default
    assert budget.angle_eps_rad == TOLERANCE_DEFAULTS["angle_eps_rad"].default
    expected_shares = tuple(
        (part, TOLERANCE_DEFAULTS[f"share_{part}"].default)
        for part in ("geometry", "fit", "control", "reserve")
    )
    assert budget.stage_shares == expected_shares
    assert budget.stage_shares == (
        ("geometry", 0.1),
        ("fit", 0.3),
        ("control", 0.5),
        ("reserve", 0.1),
    )
