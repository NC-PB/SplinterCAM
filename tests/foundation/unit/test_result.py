# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Result.ok and diagnostic ordering (REQ-FND-004)."""

import dataclasses
from collections.abc import Iterator

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from splintercam.foundation import CANCELLED, Diagnostic, Result, Severity


@pytest.mark.req("REQ-FND-004")
def test_ok_is_true_for_a_value_with_no_diagnostics() -> None:
    result = Result(value=42)
    assert result.ok is True


@pytest.mark.req("REQ-FND-004")
def test_ok_is_true_for_a_value_with_info_or_warning_diagnostics() -> None:
    diagnostics = (
        Diagnostic(code="A", severity=Severity.INFO, message="info"),
        Diagnostic(code="B", severity=Severity.WARNING, message="warn"),
    )
    result = Result(value=1, diagnostics=diagnostics)
    assert result.ok is True


@pytest.mark.req("REQ-FND-004")
def test_ok_is_false_for_a_value_with_an_error_diagnostic() -> None:
    diagnostics = (Diagnostic(code="A", severity=Severity.ERROR, message="bad"),)
    result: Result[int] = Result(value=1, diagnostics=diagnostics)
    assert result.ok is False


@pytest.mark.req("REQ-FND-004")
def test_ok_is_false_when_the_value_is_none() -> None:
    result: Result[int] = Result(value=None)
    assert result.ok is False


@pytest.mark.req("REQ-FND-004")
def test_ok_is_false_when_value_is_none_even_with_an_error_diagnostic() -> None:
    diagnostics = (Diagnostic(code="A", severity=Severity.ERROR, message="bad"),)
    result: Result[int] = Result(value=None, diagnostics=diagnostics)
    assert result.ok is False


@pytest.mark.req("REQ-FND-007")
def test_diagnostic_is_frozen() -> None:
    diagnostic = Diagnostic(code="A", severity=Severity.INFO, message="info")
    with pytest.raises(dataclasses.FrozenInstanceError):
        diagnostic.code = "B"  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.req("REQ-FND-004")
def test_diagnostics_order_is_preserved() -> None:
    diagnostics = (
        Diagnostic(code="FIRST", severity=Severity.INFO, message="1"),
        Diagnostic(code="SECOND", severity=Severity.WARNING, message="2"),
        Diagnostic(code="THIRD", severity=Severity.ERROR, message="3"),
    )
    result = Result(value=1, diagnostics=diagnostics)
    assert tuple(d.code for d in result.diagnostics) == ("FIRST", "SECOND", "THIRD")


@pytest.mark.req("REQ-FND-004")
def test_diagnostics_passed_as_a_list_is_stored_as_a_tuple() -> None:
    diagnostics = [Diagnostic(code="A", severity=Severity.INFO, message="info")]
    result = Result(value=1, diagnostics=diagnostics)  # pyright: ignore[reportArgumentType]
    assert isinstance(result.diagnostics, tuple)
    assert result.diagnostics == (diagnostics[0],)
    # A list passed in cannot mutate the stored diagnostics or the cached `ok` afterwards.
    diagnostics.append(Diagnostic(code="B", severity=Severity.ERROR, message="bad"))
    assert result.ok is True


@pytest.mark.req("REQ-FND-004")
def test_diagnostics_passed_as_a_generator_is_stored_as_a_tuple() -> None:
    def _gen() -> Iterator[Diagnostic]:
        yield Diagnostic(code="A", severity=Severity.INFO, message="info")

    result = Result(value=1, diagnostics=_gen())  # pyright: ignore[reportArgumentType]
    assert isinstance(result.diagnostics, tuple)
    assert len(result.diagnostics) == 1


@pytest.mark.req("REQ-FND-004")
@pytest.mark.parametrize("value", [0, "", 0.0, (), np.zeros(3)])
def test_ok_is_true_for_falsy_but_present_values(value: object) -> None:
    result: Result[object] = Result(value=value)
    assert result.ok is True


@pytest.mark.req("REQ-FND-004")
@given(
    value=st.one_of(st.none(), st.integers(), st.text()),
    severities=st.lists(st.sampled_from(list(Severity))),
)
def test_ok_matches_its_definition_for_any_value_and_severities(
    value: object, severities: list[Severity]
) -> None:
    diagnostics = tuple(
        Diagnostic(code="C", severity=severity, message="m") for severity in severities
    )
    result: Result[object] = Result(value=value, diagnostics=diagnostics)
    assert result.ok == (value is not None and Severity.ERROR not in severities)


@pytest.mark.req("REQ-FND-013")
def test_cancelled_is_a_warning_with_the_code_cancelled() -> None:
    assert CANCELLED.code == "CANCELLED"
    assert CANCELLED.severity is Severity.WARNING
    assert CANCELLED.message.strip()
    assert CANCELLED.location is None
    # A warning does not make a result with a value not ok; with no value it is not ok anyway.
    assert Result(value=None, diagnostics=(CANCELLED,)).ok is False
    assert Result(value=1, diagnostics=(CANCELLED,)).ok is True
