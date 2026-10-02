# SPDX-License-Identifier: Apache-2.0
"""Unit tests for an operation's tolerance budget, research 01 tests 14 and 15 (REQ-FND-009)."""

import math
from fractions import Fraction

import pytest

from splintercam.foundation import BUDGET_PARTS, Severity, ToleranceSet

# The double nearest tol_min = 8u/0.35 = 2/875 mm (REQ-FND-009); it lies just above 2/875.
_TOL_MIN = float(Fraction(2, 875))
# tol_min rounded up to 0.1 nm, the value the refusal names (REQ-FND-009; research 01, test 15).
_TOL_MIN_NAMED = "0.0022858 mm"
# u, the grid unit of the offset kernel, as an exact rational (research 01, Tolerances).
_GRID_UNIT = Fraction("0.0001")


def _budget(tol_mm: float) -> ToleranceSet:
    """The tolerance set for_operation builds for tol_mm, which must be accepted."""
    result = ToleranceSet.for_operation(tol_mm)
    assert result.ok, result.diagnostics
    assert result.value is not None
    return result.value


def _assert_within_ulp_of_tol(actual: float, expected: Fraction, tol_mm: float) -> None:
    """Assert |actual - expected| <= one unit in the last place of tol_mm, in exact rationals.

    Each budget part is a few correctly rounded double operations on tol and decimal constants,
    so it lies within one ulp of tol of its exact value (foundation SPEC, Invariants); a decimal
    value from research 01 is that exact value up to the representation error of tol, which is
    far below one ulp of tol.
    """
    assert abs(Fraction(actual) - expected) <= Fraction(math.ulp(tol_mm)), (actual, expected)


@pytest.mark.req("REQ-FND-009")
@pytest.mark.parametrize(
    ("part", "expected_mm"),
    [
        ("geometry", "0.0016"),
        ("fit", "0.0024"),
        ("control", "0.005"),
        ("reserve", "0.001"),
    ],
)
def test_budget_part_at_tol_0_01_matches_research_test_14(part: str, expected_mm: str) -> None:
    tol_mm = 0.01
    budget = _budget(tol_mm)
    _assert_within_ulp_of_tol(budget.stage_tol_mm(part), Fraction(expected_mm), tol_mm)


@pytest.mark.req("REQ-FND-009")
def test_budget_parts_at_tol_0_01_sum_to_tol() -> None:
    tol_mm = 0.01
    budget = _budget(tol_mm)
    exact_sum = sum((Fraction(budget.stage_tol_mm(part)) for part in BUDGET_PARTS), Fraction(0))
    # The SPEC invariant: the four parts sum to tol within two ulp of tol (rounding).
    assert abs(exact_sum - Fraction(tol_mm)) <= 2 * Fraction(math.ulp(tol_mm))


@pytest.mark.req("REQ-FND-009")
def test_flatten_tol_at_tol_0_01_is_0_000397_mm() -> None:
    tol_mm = 0.01
    budget = _budget(tol_mm)
    _assert_within_ulp_of_tol(budget.flatten_tol_mm, Fraction("0.000397"), tol_mm)


@pytest.mark.req("REQ-FND-009")
def test_for_operation_keeps_tol_as_the_chord_tolerance() -> None:
    assert _budget(0.01).chord_tol_mm == 0.01


@pytest.mark.req("REQ-FND-009")
def test_named_minimum_0_0022858_is_accepted_with_a_fit_band_of_3e_8_mm() -> None:
    tol_mm = 0.0022858
    budget = _budget(tol_mm)
    # 0.35 * 0.0022858 - 8u = 0.00080003 - 0.0008 = 3e-8 mm exactly in decimals.
    _assert_within_ulp_of_tol(budget.stage_tol_mm("fit"), Fraction("3e-8"), tol_mm)


@pytest.mark.req("REQ-FND-009")
def test_double_nearest_tol_min_is_accepted_with_the_fit_band_clamped_to_zero() -> None:
    budget = _budget(_TOL_MIN)
    # SPEC, Tolerance budget: in double the band at tol_min comes out as -7e-20 mm and is clamped.
    assert budget.stage_tol_mm("fit") == 0.0


def _assert_refused_below_minimum(tol_mm: float) -> None:
    result = ToleranceSet.for_operation(tol_mm)
    assert result.value is None
    assert result.ok is False
    assert len(result.diagnostics) == 1
    (diagnostic,) = result.diagnostics
    assert diagnostic.code == "TOL_BELOW_MINIMUM"
    assert diagnostic.severity is Severity.ERROR
    assert _TOL_MIN_NAMED in diagnostic.message


@pytest.mark.req("REQ-FND-009")
def test_0_0022857_is_refused_with_tol_below_minimum_naming_0_0022858_mm() -> None:
    _assert_refused_below_minimum(0.0022857)


@pytest.mark.req("REQ-FND-009")
def test_next_double_below_tol_min_is_refused() -> None:
    _assert_refused_below_minimum(math.nextafter(_TOL_MIN, -math.inf))


@pytest.mark.req("REQ-FND-009")
@pytest.mark.parametrize("tol_mm", [_TOL_MIN, 0.01, 0.05, 1.0])
def test_topology_tol_is_two_grid_units(tol_mm: float) -> None:
    topology_tol_mm = _budget(tol_mm).topology_tol_mm
    # t_topo = 2u does not depend on tol: one doubling of the double of u = 0.0001 mm, so it lies
    # within one ulp of 0.0002 mm of the exact 2u.
    assert abs(Fraction(topology_tol_mm) - 2 * _GRID_UNIT) <= Fraction(math.ulp(0.0002))


@pytest.mark.req("REQ-FND-009")
@pytest.mark.parametrize("tol_mm", [math.nan, math.inf, -math.inf])
def test_non_finite_tol_raises_value_error(tol_mm: float) -> None:
    # SPEC, Failure modes: a programming error, not a diagnostic. The message is matched only for
    # naming the tolerance, like the ToleranceSet construction errors (REQ-FND-002).
    with pytest.raises(ValueError, match="tol"):
        ToleranceSet.for_operation(tol_mm)
