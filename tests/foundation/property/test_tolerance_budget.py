# SPDX-License-Identifier: Apache-2.0
"""Property tests for the tolerance budget: parts sum to tol, small tol refused (REQ-FND-009)."""

import math
import sys
from fractions import Fraction

import pytest
from hypothesis import assume, example, given
from hypothesis import strategies as st

from splintercam.foundation import BUDGET_PARTS, Severity, ToleranceSet

# The double nearest tol_min = 8u/0.35 = 2/875 mm (REQ-FND-009); it lies just above 2/875.
_TOL_MIN = float(Fraction(2, 875))
# The largest tol a user may set (research 01, Tolerances and Parameters).
_TOL_MAX = 1.0
_BELOW_TOL_MIN = math.nextafter(_TOL_MIN, -math.inf)
# tol_min rounded up to 0.1 nm, the value the refusal names (REQ-FND-009).
_TOL_MIN_NAMED = "0.0022858 mm"

# The decimal constants of REQ-FND-009 and REQ-FND-008 as exact rationals.
_GRID_UNIT = Fraction("0.0001")  # u
_LENGTH_EPS = Fraction("1e-6")  # eps_len
_IMPORT_ARC_DEVIATION = Fraction("0.0001")  # D-093


def _exact_parts(tol_mm: float) -> dict[str, Fraction]:
    """The four budget parts of REQ-FND-009 for tol_mm, in exact rationals."""
    tol = Fraction(tol_mm)
    arc_tol_floor_cost = max(Fraction(0), 2 * _GRID_UNIT - Fraction("0.05") * tol)
    grid_cost = 6 * _GRID_UNIT + arc_tol_floor_cost
    return {
        "geometry": Fraction("0.1") * tol + grid_cost,
        "fit": max(Fraction(0), Fraction("0.3") * tol - grid_cost),
        "control": Fraction("0.5") * tol,
        "reserve": Fraction("0.1") * tol,
    }


def _exact_flatten_tol(tol_mm: float) -> Fraction:
    """t_flat of REQ-FND-009 for tol_mm, in exact rationals."""
    return Fraction("0.05") * Fraction(tol_mm) - _IMPORT_ARC_DEVIATION - 3 * _LENGTH_EPS


_ACCEPTED_TOL = st.floats(min_value=_TOL_MIN, max_value=_TOL_MAX)
_REFUSED_TOL = st.floats(max_value=_BELOW_TOL_MIN, allow_nan=False, allow_infinity=False)


@pytest.mark.req("REQ-FND-009")
@given(tol_mm=_ACCEPTED_TOL)
@example(tol_mm=_TOL_MIN)
@example(tol_mm=_TOL_MAX)
def test_budget_parts_are_not_negative_and_sum_to_tol(tol_mm: float) -> None:
    result = ToleranceSet.for_operation(tol_mm)
    assert result.ok, result.diagnostics
    budget = result.value
    assert budget is not None
    parts = [budget.stage_tol_mm(part) for part in BUDGET_PARTS]
    assert all(part >= 0.0 for part in parts), parts
    exact_sum = sum((Fraction(part) for part in parts), Fraction(0))
    # The SPEC invariant: the four parts sum to tol within two ulp of tol (rounding).
    assert abs(exact_sum - Fraction(tol_mm)) <= 2 * Fraction(math.ulp(tol_mm))


@pytest.mark.req("REQ-FND-009")
@given(tol_mm=_ACCEPTED_TOL)
@example(tol_mm=_TOL_MIN)
@example(tol_mm=_TOL_MAX)
def test_each_budget_part_follows_its_formula_within_one_ulp_of_tol(tol_mm: float) -> None:
    budget = ToleranceSet.for_operation(tol_mm).value
    assert budget is not None
    # Each part is a few correctly rounded double operations on tol and decimal constants, so it
    # lies within one ulp of tol of its exact value; the fit band is clamped at 0.
    bound = Fraction(math.ulp(tol_mm))
    for part, expected in _exact_parts(tol_mm).items():
        actual = budget.stage_tol_mm(part)
        assert abs(Fraction(actual) - expected) <= bound, (part, actual, float(expected))


@pytest.mark.req("REQ-FND-009")
@given(tol_mm=_ACCEPTED_TOL)
@example(tol_mm=_TOL_MIN)
@example(tol_mm=_TOL_MAX)
def test_flatten_tol_is_positive_and_follows_its_formula(tol_mm: float) -> None:
    budget = ToleranceSet.for_operation(tol_mm).value
    assert budget is not None
    flatten_tol_mm = budget.flatten_tol_mm
    assert flatten_tol_mm > 0.0
    # Three correctly rounded double operations on tol and decimal constants, all smaller than
    # tol: within one ulp of tol of the exact value.
    expected = _exact_flatten_tol(tol_mm)
    assert abs(Fraction(flatten_tol_mm) - expected) <= Fraction(math.ulp(tol_mm))


@pytest.mark.req("REQ-FND-009")
@given(tol_mm=_REFUSED_TOL)
@example(tol_mm=_BELOW_TOL_MIN)
@example(tol_mm=0.0022857)
@example(tol_mm=5e-324)
@example(tol_mm=0.0)
@example(tol_mm=-0.0)
@example(tol_mm=-1.0)
@example(tol_mm=-sys.float_info.max)
def test_tol_below_tol_min_is_refused_with_tol_below_minimum(tol_mm: float) -> None:
    result = ToleranceSet.for_operation(tol_mm)
    assert result.value is None
    assert result.ok is False
    assert len(result.diagnostics) == 1
    (diagnostic,) = result.diagnostics
    assert diagnostic.code == "TOL_BELOW_MINIMUM"
    assert diagnostic.severity is Severity.ERROR
    assert _TOL_MIN_NAMED in diagnostic.message


@pytest.mark.req("REQ-FND-002")
@pytest.mark.req("REQ-FND-009")
@given(
    tol_mm=st.floats(min_value=1e-4, max_value=_TOL_MAX),
    length_eps_mm=st.floats(min_value=1e-9, max_value=1e-3),
    values=st.tuples(
        st.floats(min_value=0.0, max_value=0.45),
        st.floats(min_value=0.0, max_value=0.2),
        st.floats(min_value=0.0, max_value=0.45),
        st.floats(min_value=0.0, max_value=0.1),
    ),
)
# Shares that summed to more than tol after the clamp at 0.011 mm (spec review); here above
# their floor, 6u / 0.03 = 0.02 mm.
@example(tol_mm=0.03, length_eps_mm=1e-6, values=(0.42, 0.03, 0.45, 0.1))
def test_the_parts_of_any_accepted_set_never_sum_to_more_than_tol(
    tol_mm: float, length_eps_mm: float, values: tuple[float, float, float, float]
) -> None:
    try:
        budget = ToleranceSet(
            chord_tol_mm=tol_mm,
            length_eps_mm=length_eps_mm,
            angle_eps_rad=1e-9,
            stage_shares=tuple(zip(BUDGET_PARTS, values, strict=True)),
        )
    except ValueError:
        assume(False)  # shares over 1, tol below the floor or t_flat not positive: refused
        raise
    parts = [budget.stage_tol_mm(part) for part in BUDGET_PARTS]
    assert all(part >= 0.0 for part in parts), parts
    assert budget.flatten_tol_mm > 0.0
    # Two ulps of tol for the rounding of the parts, as the foundation SPEC's invariant allows.
    assert sum(Fraction(part) for part in parts) <= Fraction(tol_mm) + 2 * Fraction(
        math.ulp(tol_mm)
    )
