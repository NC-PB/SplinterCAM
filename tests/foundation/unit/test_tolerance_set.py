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


def _tolerance_set(
    chord_tol_mm: float = 0.01, stage_shares: _Shares = _RESEARCH_SHARES
) -> ToleranceSet:
    return ToleranceSet(
        chord_tol_mm=chord_tol_mm,
        length_eps_mm=_LENGTH_EPS_MM,
        angle_eps_rad=_ANGLE_EPS_RAD,
        stage_shares=stage_shares,
    )


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


def _exact_grid_cost_mm(tol_mm: float) -> Fraction:
    # What D-146 moves from the fit band to geometry, as exact decimals (research 01, Tolerances):
    # 6u + max(0, 2u - 0.05·tol), with u = 0.0001 mm.
    u = Fraction("0.0001")
    return 6 * u + max(Fraction(0), 2 * u - Fraction("0.05") * Fraction(tol_mm))


@pytest.mark.req("REQ-FND-009")
@pytest.mark.parametrize(
    ("chord_tol_mm", "geometry_share", "fit_share"),
    [
        (0.01, 0.2, 0.4),  # 0.05·tol >= 2u: no floor term
        (0.003, 0.2, 0.4),  # 0.05·tol < 2u: the floor term applies
        # The fit band is negative before the clamp, though tol lies above the floor of
        # REQ-FND-002 for this fit share, 0.01 mm.
        (0.011, 0.1, 0.03),
    ],
)
def test_geometry_fit_and_flatten_tol_follow_the_sets_own_shares(
    chord_tol_mm: float, geometry_share: float, fit_share: float
) -> None:
    shares: _Shares = (
        ("geometry", geometry_share),
        ("fit", fit_share),
        ("control", 0.25),
        ("reserve", 0.125),
    )
    tolerances = _tolerance_set(chord_tol_mm=chord_tol_mm, stage_shares=shares)
    tol = Fraction(chord_tol_mm)
    cost = _exact_grid_cost_mm(chord_tol_mm)
    expected = {
        "geometry": Fraction(geometry_share) * tol + cost,
        "fit": max(Fraction(0), Fraction(fit_share) * tol - cost),
        # t_flat: geometry's share less the arc tolerance share 0.05, less 0.0001 mm and 3·eps_len.
        "flatten": (Fraction(geometry_share) - Fraction("0.05")) * tol
        - Fraction("0.0001")
        - 3 * Fraction(_LENGTH_EPS_MM),
    }
    actual = {
        "geometry": tolerances.stage_tol_mm("geometry"),
        "fit": tolerances.stage_tol_mm("fit"),
        "flatten": tolerances.flatten_tol_mm,
    }
    # A few correctly rounded double operations on values below tol: within one ulp of tol.
    for name, value in expected.items():
        assert abs(Fraction(actual[name]) - value) <= Fraction(math.ulp(chord_tol_mm)), name


@pytest.mark.req("REQ-FND-001")
@pytest.mark.parametrize("stage", ["offset", "fitting", "Geometry", "geometry ", ""])
def test_stage_tol_mm_rejects_an_unknown_stage(stage: str) -> None:
    tolerances = _tolerance_set()
    with pytest.raises(ValueError, match="unknown stage"):
        tolerances.stage_tol_mm(stage)


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
