# SPDX-License-Identifier: Apache-2.0
"""Property tests for ToleranceSet construction: invalid inputs always rejected (REQ-FND-002)."""

import math
import sys
from fractions import Fraction

import pytest
from hypothesis import given
from hypothesis import strategies as st

from splintercam.foundation import BUDGET_PARTS, ToleranceSet

type _Shares = tuple[tuple[str, float], ...]

# Test inputs: eps_len and eps_ang (research 01, Tolerances), and the shares of
# D-056 in BUDGET_PARTS order, whose exact sum is 1 (0.1 + 0.3 + 0.5 + 0.1 as doubles).
_LENGTH_EPS_MM = 1e-6
_ANGLE_EPS_RAD = 1e-9
# 1 mm lies above the floor of REQ-FND-002 for every fit share, (6 + 2)·u / (fit share + 0.05)
# <= 8u / 0.05 = 0.016 mm, so these tests see only the rule they check.
_CHORD_TOL_MM = 1.0
_RESEARCH_SHARES: _Shares = (("geometry", 0.1), ("fit", 0.3), ("control", 0.5), ("reserve", 0.1))


def _build(
    stage_shares: _Shares,
    *,
    chord_tol_mm: float = _CHORD_TOL_MM,
    length_eps_mm: float = _LENGTH_EPS_MM,
    angle_eps_rad: float = _ANGLE_EPS_RAD,
) -> ToleranceSet:
    return ToleranceSet(
        chord_tol_mm=chord_tol_mm,
        length_eps_mm=length_eps_mm,
        angle_eps_rad=angle_eps_rad,
        stage_shares=stage_shares,
    )


def _shares(*values: float) -> _Shares:
    """Pair four share values with BUDGET_PARTS, in that order."""
    return tuple(zip(BUDGET_PARTS, values, strict=True))


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
_VALID_TOLERANCE = _finite_floats(min_value=5e-324, max_value=sys.float_info.max)
_PART = st.sampled_from(BUDGET_PARTS)
_UNKNOWN_PART = st.text(max_size=12).filter(lambda name: name not in BUDGET_PARTS)


@pytest.mark.req("REQ-FND-002")
@given(bad=_NON_FINITE_OR_NON_POSITIVE_TOLERANCE)
def test_non_positive_or_non_finite_length_eps_is_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="length_eps_mm"):
        _build(_RESEARCH_SHARES, length_eps_mm=bad)


@pytest.mark.req("REQ-FND-002")
@given(bad=_NON_FINITE_OR_NON_POSITIVE_TOLERANCE)
def test_non_positive_or_non_finite_angle_eps_is_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="angle_eps_rad"):
        _build(_RESEARCH_SHARES, angle_eps_rad=bad)


@pytest.mark.req("REQ-FND-002")
@given(bad=_NON_FINITE_OR_NON_POSITIVE_TOLERANCE)
def test_non_positive_or_non_finite_chord_tol_is_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match="chord_tol_mm"):
        _build(_RESEARCH_SHARES, chord_tol_mm=bad)


@pytest.mark.req("REQ-FND-002")
@given(part=_PART, bad_share=_NEGATIVE_OR_NON_FINITE_SHARE)
def test_negative_nan_or_infinite_share_is_rejected(part: str, bad_share: float) -> None:
    shares = tuple((name, bad_share if name == part else 0.0) for name in BUDGET_PARTS)
    with pytest.raises(ValueError, match="stage_shares"):
        _build(shares)


@pytest.mark.req("REQ-FND-002")
@given(
    full_part=_PART,
    extra_part=_PART,
    extra=_finite_floats(min_value=1e-9, max_value=1.0),
)
def test_shares_summing_to_more_than_one_are_rejected(
    full_part: str, extra_part: str, extra: float
) -> None:
    values = dict.fromkeys(BUDGET_PARTS, 0.0)
    values[full_part] = 1.0
    values[extra_part] += extra
    shares = tuple(values.items())
    with pytest.raises(ValueError, match="sum to at most 1"):
        _build(shares)


@pytest.mark.req("REQ-FND-002")
@given(present=st.lists(_PART, unique=True, max_size=len(BUDGET_PARTS) - 1))
def test_a_missing_budget_part_is_rejected(present: list[str]) -> None:
    research = dict(_RESEARCH_SHARES)
    shares = tuple((part, research[part]) for part in present)
    with pytest.raises(ValueError, match="stage_shares"):
        _build(shares)


@pytest.mark.req("REQ-FND-002")
@given(unknown=_UNKNOWN_PART, replaced=st.one_of(st.none(), _PART), position=st.integers(0, 4))
def test_an_unknown_budget_part_is_rejected(
    unknown: str, replaced: str | None, position: int
) -> None:
    # The unknown part is either added to the four (replaced is None) or takes the place of one;
    # its share is 0, so the shares alone would be valid.
    shares = [pair for pair in _RESEARCH_SHARES if pair[0] != replaced]
    shares.insert(min(position, len(shares)), (unknown, 0.0))
    with pytest.raises(ValueError, match="stage_shares"):
        _build(tuple(shares))


@pytest.mark.req("REQ-FND-002")
@pytest.mark.parametrize(
    "shares",
    [
        (*_RESEARCH_SHARES, ("fit", 0.0)),  # a fifth pair
        (("geometry", 0.1), ("fit", 0.3), ("control", 0.5), ("fit", 0.0)),  # in place of reserve
    ],
)
def test_a_budget_part_given_twice_is_rejected(shares: _Shares) -> None:
    # The second copy has share 0, so the shares alone would be valid.
    with pytest.raises(ValueError, match="stage_shares"):
        _build(shares)


@pytest.mark.req("REQ-FND-002")
@given(
    length_eps=_VALID_TOLERANCE,
    angle_eps=_VALID_TOLERANCE,
    chord_tol=_finite_floats(min_value=0.02, max_value=sys.float_info.max),  # above the floor
    values=st.tuples(*(_finite_floats(min_value=0.0, max_value=0.25) for _ in BUDGET_PARTS)),
    order=st.permutations(range(len(BUDGET_PARTS))),
)
def test_valid_tolerance_sets_are_accepted(
    length_eps: float,
    angle_eps: float,
    chord_tol: float,
    values: tuple[float, ...],
    order: list[int],
) -> None:
    expected = _shares(*values)
    tolerances = _build(
        tuple(expected[i] for i in order),
        chord_tol_mm=chord_tol,
        length_eps_mm=length_eps,
        angle_eps_rad=angle_eps,
    )
    assert tolerances.length_eps_mm == length_eps
    assert tolerances.angle_eps_rad == angle_eps
    assert tolerances.chord_tol_mm == chord_tol
    assert tolerances.stage_shares == expected


@pytest.mark.req("REQ-FND-002")
@given(
    values=st.tuples(*(st.floats(min_value=0.0, max_value=1.0) for _ in BUDGET_PARTS)),
    order=st.permutations(range(len(BUDGET_PARTS))),
)
def test_share_acceptance_matches_the_exact_fraction_sum(
    values: tuple[float, ...], order: list[int]
) -> None:
    pairs = _shares(*values)
    shares = tuple(pairs[i] for i in order)
    if sum(Fraction(value) for value in values) > 1:
        with pytest.raises(ValueError, match="sum to at most 1"):
            _build(shares)
    else:
        assert _build(shares).stage_shares == pairs


@pytest.mark.req("REQ-FND-002")
@pytest.mark.parametrize(
    ("values", "should_be_accepted"),
    [
        ((1.0, 0.0, 0.0, 0.0), True),
        ((0.5, 0.5, 0.0, 0.0), True),
        ((0.25, 0.25, 0.5, 0.0), True),
        ((0.1, 0.3, 0.5, 0.1), True),  # D-056's shares: exactly 1 as doubles
        ((1.0, 1e-17, 0.0, 0.0), False),
        ((1.0, 5e-324, 0.0, 0.0), False),
        ((0.5, math.nextafter(0.5, 1.0), 0.0, 0.0), False),
        ((0.1, 0.3, 0.5, math.nextafter(0.1, 1.0)), False),
    ],
)
def test_shares_summing_to_exactly_or_just_over_one(
    values: tuple[float, float, float, float], should_be_accepted: bool
) -> None:
    shares = _shares(*values)
    if should_be_accepted:
        assert _build(shares).stage_shares == shares
    else:
        with pytest.raises(ValueError, match="sum to at most 1"):
            _build(shares)


def _exact_floor_mm(fit_share: float) -> Fraction:
    # REQ-FND-002 (Peter, 2026-10-02): tol_min of the own shares, (6 + 2)·u / (fit share + 0.05),
    # with u = 0.0001 mm (research 01, Tolerances), in exact rationals.
    return 8 * Fraction("0.0001") / (Fraction(fit_share) + Fraction("0.05"))


@pytest.mark.req("REQ-FND-002")
@pytest.mark.parametrize("fit_share", [0.0, 0.03, 0.1, 0.3, 0.4])
def test_a_chord_tolerance_below_the_floor_of_its_own_shares_is_rejected(fit_share: float) -> None:
    shares = _shares(0.1, fit_share, 0.5, 0.1)
    floor = _exact_floor_mm(fit_share)
    # One per cent either side: the floor itself is a double computed once, so its exact bits
    # are checked through for_operation at the default shares (research 01, test 15).
    with pytest.raises(ValueError, match="chord_tol_mm"):
        _build(shares, chord_tol_mm=float(floor * Fraction(99, 100)))
    assert _build(shares, chord_tol_mm=float(floor * Fraction(101, 100))).chord_tol_mm > 0
