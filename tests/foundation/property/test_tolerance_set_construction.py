# SPDX-License-Identifier: Apache-2.0
"""Property tests for ToleranceSet construction: invalid inputs always rejected (REQ-FND-002)."""

import math
import sys
from fractions import Fraction

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from splintercam.foundation import BUDGET_PARTS, ToleranceSet

type _Shares = tuple[tuple[str, float], ...]

# Test inputs: eps_len and eps_ang (research 01, Tolerances), and the shares of
# D-056 in BUDGET_PARTS order, whose exact sum is 1 (0.1 + 0.3 + 0.5 + 0.1 as doubles).
_LENGTH_EPS_MM = 1e-6
_ANGLE_EPS_RAD = 1e-9
# 1 mm: the share tests below see the floor and t_flat of REQ-FND-002 only for a fit share under
# 0.0006 or a geometry share under about 0.0501; `_expected_refusal` predicts those refusals.
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


def _built_or_refusal(stage_shares: _Shares) -> ToleranceSet | str:
    """The set at 1 mm, or "floor" or "t_flat" when that rule of REQ-FND-002 refuses it."""
    try:
        return _build(stage_shares)
    except ValueError as error:
        if "t_flat" in str(error):
            return "t_flat"
        if "chord_tol_mm must be >=" in str(error):
            return "floor"
        raise


def _expected_refusal(geometry_share: float, fit_share: float) -> str | None:
    """The rule of REQ-FND-002 that refuses shares summing to at most 1 at 1 mm, exactly."""
    tol = Fraction(_CHORD_TOL_MM)
    if fit_share == 0.0 or _exact_floor_mm(fit_share) > tol:
        return "floor"
    if (Fraction(geometry_share) - Fraction("0.05")) * tol <= _exact_zero_flatten_allowance():
        return "t_flat"
    return None


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
    length_eps=_finite_floats(min_value=5e-324, max_value=1.0),
    angle_eps=_VALID_TOLERANCE,
    data=st.data(),
    # A geometry share above 0.05 and a fit share above 0: otherwise no tol is valid. The lower
    # ends keep the smallest valid tol finite, at most 3.0001 mm / 0.0001 = 30001 mm.
    values=st.tuples(
        _finite_floats(min_value=0.0501, max_value=0.25),
        _finite_floats(min_value=1e-4, max_value=0.25),
        _finite_floats(min_value=0.0, max_value=0.25),
        _finite_floats(min_value=0.0, max_value=0.25),
    ),
    order=st.permutations(range(len(BUDGET_PARTS))),
)
def test_valid_tolerance_sets_are_accepted(
    length_eps: float,
    angle_eps: float,
    data: st.DataObject,
    values: tuple[float, ...],
    order: list[int],
) -> None:
    expected = _shares(*values)
    # From one per cent above the floor of the drawn fit share and the tol where t_flat is 0
    # upward (REQ-FND-002).
    lowest = max(_exact_floor_mm(values[1]), _exact_zero_flatten_tol_mm(values[0], length_eps))
    floor = float(lowest * Fraction(101, 100))
    chord_tol = data.draw(_finite_floats(min_value=floor, max_value=sys.float_info.max))
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
        built = _built_or_refusal(shares)
        expected = _expected_refusal(values[0], values[1])
        if expected is None:
            assert isinstance(built, ToleranceSet)
            assert built.stage_shares == pairs
        else:
            assert built == expected


@pytest.mark.req("REQ-FND-002")
@pytest.mark.parametrize(
    ("values", "should_be_accepted"),
    [
        ((1.0, 0.0, 0.0, 0.0), "floor"),  # accepted shares, but fit share 0: refused by the floor
        ((0.75, 0.25, 0.0, 0.0), True),  # exactly 1, one share dominant
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
    values: tuple[float, float, float, float], should_be_accepted: bool | str
) -> None:
    shares = _shares(*values)
    if isinstance(should_be_accepted, str):
        assert _built_or_refusal(shares) == should_be_accepted
    elif should_be_accepted:
        assert _build(shares).stage_shares == shares
    else:
        with pytest.raises(ValueError, match="sum to at most 1"):
            _build(shares)


_U = Fraction("0.0001")  # the grid unit u (research 01, Tolerances)


def _exact_floor_mm(fit_share: float) -> Fraction:
    # REQ-FND-002 (Peter, 2026-10-02), in exact rationals: 8u / (fit share + 0.05) for a fit
    # share of 0.15 or more, else 6u / fit share. Fit share > 0.
    fit = Fraction(fit_share)
    return 8 * _U / (fit + Fraction("0.05")) if fit >= Fraction("0.15") else 6 * _U / fit


def _exact_zero_flatten_allowance(length_eps_mm: float = _LENGTH_EPS_MM) -> Fraction:
    # What t_flat = (geometry share - 0.05)·tol - 0.0001 mm - 3·eps_len takes from geometry
    # besides the arc tolerance share (REQ-FND-009; research 01, Tolerances).
    return Fraction("0.0001") + 3 * Fraction(length_eps_mm)


def _exact_zero_flatten_tol_mm(geometry_share: float, length_eps_mm: float) -> Fraction:
    # The tol where t_flat is 0; geometry share > 0.05.
    allowance = _exact_zero_flatten_allowance(length_eps_mm)
    return allowance / (Fraction(geometry_share) - Fraction("0.05"))


@pytest.mark.req("REQ-FND-002")
@pytest.mark.parametrize("fit_share", [0.03, 0.1, 0.15, 0.3, 0.4])
def test_a_chord_tolerance_below_the_floor_of_its_own_shares_is_rejected(fit_share: float) -> None:
    # Geometry share 0.2: t_flat > 0 from 0.000687 mm, below every floor here (at most 0.02 mm);
    # the shares sum to at most 0.95. Only the floor is tested.
    shares = _shares(0.2, fit_share, 0.25, 0.1)
    floor = _exact_floor_mm(fit_share)
    # One per cent either side: the floor itself is a double computed once, so its exact bits
    # are checked through for_operation at the default shares (research 01, test 15).
    with pytest.raises(ValueError, match="chord_tol_mm must be >="):
        _build(shares, chord_tol_mm=float(floor * Fraction(99, 100)))
    assert _build(shares, chord_tol_mm=float(floor * Fraction(101, 100))).chord_tol_mm > 0


@pytest.mark.req("REQ-FND-002")
@given(
    fit_share=st.floats(min_value=0.001, max_value=0.4),
    below=st.booleans(),
    distance=st.fractions(min_value=Fraction(1, 100), max_value=10),
)
def test_the_floor_of_any_fit_share_separates_rejected_from_accepted(
    fit_share: float, below: bool, distance: Fraction
) -> None:
    shares = _shares(0.2, fit_share, 0.25, 0.1)  # as above: only the floor is tested
    floor = _exact_floor_mm(fit_share)
    if below:
        with pytest.raises(ValueError, match="chord_tol_mm must be >="):
            _build(shares, chord_tol_mm=float(floor / (1 + distance)))
    else:
        chord_tol = float(floor * (1 + distance))
        assert _build(shares, chord_tol_mm=chord_tol).chord_tol_mm == chord_tol


@pytest.mark.req("REQ-FND-002")
def test_the_constructor_refuses_the_double_just_below_the_floor_of_the_default_shares() -> None:
    # for_operation refuses below tol_min first, so the constructor's own edge is checked here:
    # the floor at fit share 0.3 is the double nearest 2/875 mm (research 01, test 15).
    floor = float(Fraction(2, 875))
    with pytest.raises(ValueError, match="chord_tol_mm must be >="):
        _build(_RESEARCH_SHARES, chord_tol_mm=math.nextafter(floor, 0.0))
    assert _build(_RESEARCH_SHARES, chord_tol_mm=floor).chord_tol_mm == floor


@pytest.mark.req("REQ-FND-002")
@given(chord_tol=_VALID_TOLERANCE)
def test_a_fit_share_of_0_is_rejected_at_any_tolerance(chord_tol: float) -> None:
    # 6u / 0: no tol leaves the fit band at 0 or above (Peter, 2026-10-02).
    with pytest.raises(ValueError, match="chord_tol_mm must be >="):
        _build(_shares(0.2, 0.0, 0.5, 0.1), chord_tol_mm=chord_tol)


@pytest.mark.req("REQ-FND-002")
@given(
    geometry_share=st.floats(min_value=0.0, max_value=0.5),
    length_eps=st.floats(min_value=1e-9, max_value=1e-2),
    chord_tol=st.floats(min_value=0.003, max_value=1.0),
)
def test_t_flat_separates_rejected_from_accepted(
    geometry_share: float, length_eps: float, chord_tol: float
) -> None:
    # Fit share 0.3: the floor, 0.0022857 mm, lies below every tol drawn; only t_flat is tested.
    shares = _shares(geometry_share, 0.3, 0.1, 0.1)
    exact_t_flat = (Fraction(geometry_share) - Fraction("0.05")) * Fraction(
        chord_tol
    ) - _exact_zero_flatten_allowance(length_eps)
    # Within a few ulps of tol of 0, the double t_flat may round to either side.
    assume(abs(exact_t_flat) > 4 * Fraction(math.ulp(chord_tol)))
    if exact_t_flat > 0:
        built = _build(shares, chord_tol_mm=chord_tol, length_eps_mm=length_eps)
        assert built.flatten_tol_mm > 0.0
    else:
        with pytest.raises(ValueError, match="t_flat"):
            _build(shares, chord_tol_mm=chord_tol, length_eps_mm=length_eps)
