# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ToleranceSet fields, budget parts, stage_tol_mm and immutability (REQ-FND-001)."""

import copy
import dataclasses
import math
import pickle
import typing
from fractions import Fraction

import pytest

from splintercam.foundation import BUDGET_PARTS, ToleranceSet

type _Shares = tuple[tuple[str, float], ...]

# Test inputs, not comparison tolerances: eps_len and eps_ang (research 01, Tolerances, Q-034
# answer) and the shares of D-056 (research 01, Tolerances, the budget table), in BUDGET_PARTS
# order.
_LENGTH_EPS_MM = 1e-6
_ANGLE_EPS_RAD = 1e-9
_RESEARCH_SHARES: _Shares = (("geometry", 0.1), ("fit", 0.3), ("control", 0.5), ("reserve", 0.1))

# The oracle's constants for the grid cost D-146 adds to geometry and takes from the fit band
# (research 01, Tolerances: geometry = share·tol + 6u + max(0, 2u - 0.05·tol)), as exact decimals.
_GRID_UNIT_MM = Fraction("0.0001")  # u (D-058, D-132)
_ROUNDING_MARGIN_GRID_UNITS = 6  # D-132
_ARC_TOL_SHARE = Fraction("0.05")  # a = max(0.05·tol, 2u) (D-058)
_ARC_TOL_FLOOR_GRID_UNITS = 2  # D-058


def _tolerance_set(
    chord_tol_mm: float = 0.01, stage_shares: _Shares = _RESEARCH_SHARES
) -> ToleranceSet:
    return ToleranceSet(
        chord_tol_mm=chord_tol_mm,
        length_eps_mm=_LENGTH_EPS_MM,
        angle_eps_rad=_ANGLE_EPS_RAD,
        stage_shares=stage_shares,
    )


def _exact_grid_cost_mm(tol_mm: float) -> Fraction:
    floor_term = _ARC_TOL_FLOOR_GRID_UNITS * _GRID_UNIT_MM - _ARC_TOL_SHARE * Fraction(tol_mm)
    return _ROUNDING_MARGIN_GRID_UNITS * _GRID_UNIT_MM + max(Fraction(0), floor_term)


def _one_ulp_of(tol_mm: float) -> Fraction:
    # Each part is a few correctly rounded double operations on values no larger than tol, so it
    # lies within one unit in the last place of tol of its exact value (foundation SPEC,
    # Invariants: the four parts sum to tol within two ulp of tol). The double nearest u differs
    # from the decimal u by about 5e-21 mm, far below one ulp of any tol tested here.
    return Fraction(math.ulp(tol_mm))


@pytest.mark.req("REQ-FND-001")
def test_budget_parts_are_geometry_fit_control_reserve_in_that_order() -> None:
    assert BUDGET_PARTS == ("geometry", "fit", "control", "reserve")


@pytest.mark.req("REQ-FND-001")
def test_tolerance_set_exposes_its_fields() -> None:
    tolerances = _tolerance_set()
    assert tolerances.chord_tol_mm == 0.01
    assert tolerances.length_eps_mm == _LENGTH_EPS_MM
    assert tolerances.angle_eps_rad == _ANGLE_EPS_RAD
    assert tolerances.stage_shares == _RESEARCH_SHARES


@pytest.mark.req("REQ-FND-001")
def test_stage_shares_are_stored_in_budget_parts_order_whatever_the_input_order() -> None:
    reversed_input = tuple(reversed(_RESEARCH_SHARES))
    tolerances = _tolerance_set(stage_shares=reversed_input)
    assert tuple(part for part, _ in tolerances.stage_shares) == BUDGET_PARTS
    assert tolerances.stage_shares == _RESEARCH_SHARES


@pytest.mark.req("REQ-FND-001")
@pytest.mark.parametrize("chord_tol_mm", [0.01, 0.05, 0.003, 1.0])
@pytest.mark.parametrize("part", ["control", "reserve"])
def test_control_and_reserve_stage_tol_are_their_share_of_chord_tolerance(
    part: str, chord_tol_mm: float
) -> None:
    tolerances = _tolerance_set(chord_tol_mm=chord_tol_mm)
    share = dict(_RESEARCH_SHARES)[part]
    # Compared exactly: share·tol is a single IEEE multiplication (foundation SPEC, Tolerance
    # budget: control and reserve are their share of tol), so it needs no tolerance of its own.
    assert tolerances.stage_tol_mm(part) == share * chord_tol_mm


@pytest.mark.req("REQ-FND-001")
def test_control_and_reserve_stage_tol_follow_non_default_shares() -> None:
    shares: _Shares = (("geometry", 0.2), ("fit", 0.4), ("control", 0.25), ("reserve", 0.125))
    tolerances = _tolerance_set(chord_tol_mm=0.02, stage_shares=shares)
    # Exact for the reason above.
    assert tolerances.stage_tol_mm("control") == 0.25 * 0.02
    assert tolerances.stage_tol_mm("reserve") == 0.125 * 0.02


@pytest.mark.req("REQ-FND-009")
def test_geometry_and_fit_stage_tol_at_finishing_tolerance_match_the_spec_numbers() -> None:
    # Foundation SPEC, Tolerance budget, and research 01 test 14: at tol = 0.01 mm the parts are
    # 0.0016 + 0.0024 + 0.005 + 0.001 mm.
    tolerances = _tolerance_set(chord_tol_mm=0.01)
    bound = _one_ulp_of(0.01)
    assert abs(Fraction(tolerances.stage_tol_mm("geometry")) - Fraction("0.0016")) <= bound
    assert abs(Fraction(tolerances.stage_tol_mm("fit")) - Fraction("0.0024")) <= bound


@pytest.mark.req("REQ-FND-009")
@pytest.mark.parametrize(
    "chord_tol_mm",
    [
        0.01,  # 0.05·tol ≥ 2u: no floor term
        0.05,  # roughing default (D-029)
        1.0,  # the user's upper limit (research 01, Parameters)
        0.003,  # 0.05·tol < 2u: the floor term max(0, 2u - 0.05·tol) applies
    ],
)
def test_geometry_adds_and_fit_subtracts_the_grid_cost(chord_tol_mm: float) -> None:
    tolerances = _tolerance_set(chord_tol_mm=chord_tol_mm)
    shares = dict(_RESEARCH_SHARES)
    tol = Fraction(chord_tol_mm)
    cost = _exact_grid_cost_mm(chord_tol_mm)
    expected_geometry = Fraction(shares["geometry"]) * tol + cost
    expected_fit = Fraction(shares["fit"]) * tol - cost
    assert expected_fit > 0  # the clamp does not apply to these tolerances
    bound = _one_ulp_of(chord_tol_mm)
    assert abs(Fraction(tolerances.stage_tol_mm("geometry")) - expected_geometry) <= bound
    assert abs(Fraction(tolerances.stage_tol_mm("fit")) - expected_fit) <= bound


@pytest.mark.req("REQ-FND-009")
@pytest.mark.parametrize("fit_share", [0.0, 0.03])
def test_fit_stage_tol_is_clamped_at_zero_when_its_share_is_below_the_grid_cost(
    fit_share: float,
) -> None:
    # At tol = 0.01 mm the grid cost is 6u = 0.0006 mm; a fit share of 0 or 0.03 leaves at most
    # 0.0003 mm before the cost, so the band is negative before the clamp (foundation SPEC,
    # Tolerance budget: fit is its share minus the grid cost, clamped at 0).
    shares: _Shares = (("geometry", 0.1), ("fit", fit_share), ("control", 0.5), ("reserve", 0.1))
    tolerances = _tolerance_set(chord_tol_mm=0.01, stage_shares=shares)
    assert tolerances.stage_tol_mm("fit") == 0.0
    expected_geometry = Fraction(0.1) * Fraction(0.01) + _exact_grid_cost_mm(0.01)
    assert abs(Fraction(tolerances.stage_tol_mm("geometry")) - expected_geometry) <= _one_ulp_of(
        0.01
    )


@pytest.mark.req("REQ-FND-001")
@pytest.mark.parametrize("stage", ["offset", "fitting", "Geometry", "geometry ", ""])
def test_stage_tol_mm_rejects_an_unknown_stage(stage: str) -> None:
    tolerances = _tolerance_set()
    with pytest.raises(ValueError, match="unknown stage"):
        tolerances.stage_tol_mm(stage)


@pytest.mark.req("REQ-FND-007")
def test_stage_shares_is_a_tuple_of_pairs() -> None:
    tolerances = _tolerance_set(stage_shares=tuple(reversed(_RESEARCH_SHARES)))
    assert type(tolerances.stage_shares) is tuple
    assert all(type(pair) is tuple and len(pair) == 2 for pair in tolerances.stage_shares)


@pytest.mark.req("REQ-FND-007")
def test_stage_shares_cannot_be_written_to() -> None:
    tolerances = _tolerance_set()
    mutable_view = typing.cast("list[tuple[str, float]]", tolerances.stage_shares)
    with pytest.raises(TypeError):
        mutable_view[0] = ("geometry", 0.9)
    mutable_pair = typing.cast("list[object]", tolerances.stage_shares[0])
    with pytest.raises(TypeError):
        mutable_pair[1] = 0.9
    assert tolerances.stage_shares == _RESEARCH_SHARES


@pytest.mark.req("REQ-FND-007")
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("chord_tol_mm", 0.02),
        ("length_eps_mm", 2e-6),
        ("angle_eps_rad", 2e-9),
        ("stage_shares", (("geometry", 0.2),)),
    ],
)
def test_tolerance_set_is_frozen(field: str, value: object) -> None:
    tolerances = _tolerance_set()
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(tolerances, field, value)


@pytest.mark.req("REQ-FND-007")
def test_tolerance_set_is_hashable_and_equal_sets_hash_equal() -> None:
    first = _tolerance_set()
    second = _tolerance_set()
    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.req("REQ-FND-007")
@pytest.mark.parametrize(
    "order",
    [(3, 2, 1, 0), (1, 2, 3, 0), (2, 0, 3, 1)],
)
def test_equality_and_hash_do_not_depend_on_stage_share_input_order(
    order: tuple[int, int, int, int],
) -> None:
    first = _tolerance_set()
    second = _tolerance_set(stage_shares=tuple(_RESEARCH_SHARES[i] for i in order))
    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.req("REQ-FND-001")
def test_unequal_tolerance_sets_compare_unequal() -> None:
    first = _tolerance_set()
    other_shares: _Shares = (("geometry", 0.1), ("fit", 0.3), ("control", 0.4), ("reserve", 0.1))
    assert first != _tolerance_set(stage_shares=other_shares)
    assert first != _tolerance_set(chord_tol_mm=0.05)


@pytest.mark.req("REQ-FND-001")
def test_tolerance_set_survives_pickle_round_trip() -> None:
    original = _tolerance_set(stage_shares=tuple(reversed(_RESEARCH_SHARES)))
    restored = pickle.loads(pickle.dumps(original))
    assert restored == original
    assert hash(restored) == hash(original)
    assert restored.stage_shares == original.stage_shares


@pytest.mark.req("REQ-FND-001")
def test_tolerance_set_survives_deepcopy() -> None:
    original = _tolerance_set(stage_shares=tuple(reversed(_RESEARCH_SHARES)))
    copied = copy.deepcopy(original)
    assert copied == original
    assert hash(copied) == hash(original)
    assert copied.stage_shares == original.stage_shares
