# SPDX-License-Identifier: Apache-2.0
"""Property tests for ToleranceSet construction: invalid inputs always rejected (REQ-FND-002)."""

import fractions
import math
import sys

import pytest
from hypothesis import given
from hypothesis import strategies as st

from splintercam.foundation import ToleranceSet


def _finite_floats(
    *, min_value: float | None = None, max_value: float | None = None
) -> st.SearchStrategy[float]:
    return st.floats(
        min_value=min_value, max_value=max_value, allow_nan=False, allow_infinity=False
    )


_NON_FINITE_OR_NON_POSITIVE_TOLERANCE = st.one_of(
    _finite_floats(max_value=0.0),  # non-positive, including zero
    st.sampled_from([math.nan, math.inf, -math.inf]),
)
_NEGATIVE_OR_NON_FINITE_SHARE = st.one_of(
    # max_value=-5e-324 excludes -0.0, which is not negative, and reaches up to the negative
    # float closest to zero.
    _finite_floats(max_value=-5e-324),
    st.sampled_from([math.nan, math.inf, -math.inf]),
)


@pytest.mark.req("REQ-FND-002")
@given(bad=_NON_FINITE_OR_NON_POSITIVE_TOLERANCE)
def test_non_positive_or_non_finite_length_eps_is_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="length_eps_mm"):
        ToleranceSet(length_eps_mm=bad, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={})


@pytest.mark.req("REQ-FND-002")
@given(bad=_NON_FINITE_OR_NON_POSITIVE_TOLERANCE)
def test_non_positive_or_non_finite_angle_eps_is_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="angle_eps_rad"):
        ToleranceSet(length_eps_mm=1e-6, angle_eps_rad=bad, chord_tol_mm=0.01, stage_shares={})


@pytest.mark.req("REQ-FND-002")
@given(bad=_NON_FINITE_OR_NON_POSITIVE_TOLERANCE)
def test_non_positive_or_non_finite_chord_tol_is_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="chord_tol_mm"):
        ToleranceSet(length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=bad, stage_shares={})


@pytest.mark.req("REQ-FND-002")
@given(bad_share=_NEGATIVE_OR_NON_FINITE_SHARE)
def test_negative_nan_or_infinite_share_is_rejected(bad_share: float) -> None:
    with pytest.raises(ValueError, match="stage_shares"):
        ToleranceSet(
            length_eps_mm=1e-6,
            angle_eps_rad=1e-9,
            chord_tol_mm=0.01,
            stage_shares={"offset": bad_share},
        )


@pytest.mark.req("REQ-FND-002")
@given(extra=_finite_floats(min_value=1e-9, max_value=1.0))
def test_shares_summing_to_more_than_one_are_rejected(extra: float) -> None:
    with pytest.raises(ValueError, match="sum to at most 1"):
        ToleranceSet(
            length_eps_mm=1e-6,
            angle_eps_rad=1e-9,
            chord_tol_mm=0.01,
            stage_shares={"offset": 1.0, "fitting": extra},
        )


_VALID_TOLERANCE = _finite_floats(min_value=5e-324, max_value=sys.float_info.max)


@pytest.mark.req("REQ-FND-002")
@given(
    length_eps=_VALID_TOLERANCE,
    angle_eps=_VALID_TOLERANCE,
    chord_tol=_VALID_TOLERANCE,
    share_a=_finite_floats(min_value=0.0, max_value=0.5),
    share_b=_finite_floats(min_value=0.0, max_value=0.5),
)
def test_valid_tolerance_sets_are_accepted(
    length_eps: float, angle_eps: float, chord_tol: float, share_a: float, share_b: float
) -> None:
    tolerances = ToleranceSet(
        length_eps_mm=length_eps,
        angle_eps_rad=angle_eps,
        chord_tol_mm=chord_tol,
        stage_shares={"a": share_a, "b": share_b},
    )
    assert tolerances.length_eps_mm == length_eps
    assert tolerances.angle_eps_rad == angle_eps
    assert tolerances.chord_tol_mm == chord_tol
    assert dict(tolerances.stage_shares) == {"a": share_a, "b": share_b}


@pytest.mark.req("REQ-FND-002")
@given(
    shares=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False), min_size=1, max_size=6
    )
)
def test_share_acceptance_matches_the_exact_fraction_sum(shares: list[float]) -> None:
    stage_shares = {f"stage{i}": share for i, share in enumerate(shares)}
    exact_total = sum(fractions.Fraction(share) for share in shares)
    if exact_total > 1:
        with pytest.raises(ValueError, match="sum to at most 1"):
            ToleranceSet(
                length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares=stage_shares
            )
    else:
        tolerances = ToleranceSet(
            length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares=stage_shares
        )
        assert dict(tolerances.stage_shares) == stage_shares


@pytest.mark.req("REQ-FND-002")
@pytest.mark.parametrize(
    ("shares", "should_be_accepted"),
    [
        ({"a": 1.0}, True),
        ({"a": 0.5, "b": 0.5}, True),
        ({"a": 0.25, "b": 0.25, "c": 0.5}, True),
        ({"a": 1.0, "b": 1e-17}, False),
        ({"a": 1.0, "b": 5e-324}, False),
        ({"a": 0.5, "b": math.nextafter(0.5, 1.0)}, False),
    ],
)
def test_shares_summing_to_exactly_or_just_over_one(
    shares: dict[str, float], should_be_accepted: bool
) -> None:
    if should_be_accepted:
        tolerances = ToleranceSet(
            length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares=shares
        )
        assert dict(tolerances.stage_shares) == shares
    else:
        with pytest.raises(ValueError, match="sum to at most 1"):
            ToleranceSet(
                length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares=shares
            )
