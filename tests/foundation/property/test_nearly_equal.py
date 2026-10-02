# SPDX-License-Identifier: Apache-2.0
"""Property tests for nearly_equal against its definition, NaN and infinities (REQ-FND-003)."""

import math
import warnings

import numpy as np
import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from splintercam.foundation import nearly_equal

_FINITE = st.floats(allow_nan=False, allow_infinity=False)
_NON_NEGATIVE_FINITE = st.floats(min_value=0.0, allow_nan=False, allow_infinity=False)
_ANY = st.floats()
_NON_NAN = st.floats(allow_nan=False)


@pytest.mark.req("REQ-FND-003")
@given(a=_FINITE, b=_FINITE, tol=_NON_NEGATIVE_FINITE)
@example(a=1.0, b=1.0, tol=0.0)
@example(a=1.0, b=1.5, tol=0.5)
@example(a=1.0, b=1.5, tol=math.nextafter(0.5, 0.0))
def test_nearly_equal_matches_the_definition_for_finite_inputs(
    a: float, b: float, tol: float
) -> None:
    assert nearly_equal(a, b, tol) == (abs(a - b) <= tol)


@pytest.mark.req("REQ-FND-003")
def test_nearly_equal_boundary_cases() -> None:
    assert nearly_equal(1.0, 1.0, 0.0) is True
    assert nearly_equal(1.0, 1.5, 0.5) is True
    assert nearly_equal(1.0, 1.5, math.nextafter(0.5, 0.0)) is False


@pytest.mark.req("REQ-FND-003")
@given(a=st.floats(allow_nan=False), b=st.floats(allow_nan=False))
def test_nearly_equal_returns_a_python_bool_for_numpy_scalar_inputs(a: float, b: float) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = nearly_equal(np.float64(a), np.float64(b), np.float64(1.0))
    assert type(result) is bool


@pytest.mark.req("REQ-FND-003")
def test_nearly_equal_returns_a_python_bool_for_numpy_infinities_without_warning() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = nearly_equal(np.float64(np.inf), np.float64(np.inf), np.float64(1.0))
    assert type(result) is bool
    assert result is False


@pytest.mark.req("REQ-FND-003")
@given(other=_ANY, tol=_ANY)
def test_nearly_equal_is_false_when_the_first_argument_is_nan(other: float, tol: float) -> None:
    assert nearly_equal(math.nan, other, tol) is False


@pytest.mark.req("REQ-FND-003")
@given(other=_ANY, tol=_ANY)
def test_nearly_equal_is_false_when_the_second_argument_is_nan(other: float, tol: float) -> None:
    assert nearly_equal(other, math.nan, tol) is False


@pytest.mark.req("REQ-FND-003")
@given(a=_NON_NAN, b=_NON_NAN)
def test_nearly_equal_is_false_when_the_tolerance_is_nan(a: float, b: float) -> None:
    assert nearly_equal(a, b, math.nan) is False


@pytest.mark.req("REQ-FND-003")
def test_nearly_equal_of_two_equal_infinities_is_false() -> None:
    # inf - inf is NaN, so the definition's own arithmetic gives False here: an open question
    # for Peter to confirm (SPEC "Open questions"), not a special case in the implementation.
    assert nearly_equal(math.inf, math.inf, 1.0) is False
    assert nearly_equal(-math.inf, -math.inf, 1.0) is False


@pytest.mark.req("REQ-FND-003")
def test_nearly_equal_of_opposite_infinities_is_false() -> None:
    assert nearly_equal(math.inf, -math.inf, 1.0) is False


@pytest.mark.req("REQ-FND-003")
@given(finite=_FINITE, tol=_NON_NEGATIVE_FINITE)
def test_nearly_equal_of_finite_and_infinite_is_false_for_finite_tolerance(
    finite: float, tol: float
) -> None:
    assert nearly_equal(math.inf, finite, tol) is False
    assert nearly_equal(finite, math.inf, tol) is False


@pytest.mark.req("REQ-FND-003")
@given(a=_FINITE, b=_FINITE)
def test_nearly_equal_with_infinite_tolerance_is_true_for_finite_inputs(a: float, b: float) -> None:
    assert nearly_equal(a, b, math.inf) is True
