# SPDX-License-Identifier: Apache-2.0
"""Unit tests for ToleranceSet field access, stage_tol_mm and its immutability (REQ-FND-001)."""

import copy
import dataclasses
import pickle
import typing

import pytest

from splintercam.foundation import ToleranceSet


@pytest.mark.req("REQ-FND-001")
def test_tolerance_set_exposes_its_fields() -> None:
    tolerances = ToleranceSet(
        length_eps_mm=1e-6,
        angle_eps_rad=1e-9,
        chord_tol_mm=0.01,
        stage_shares={"offset": 0.3, "fitting": 0.2},
    )
    assert tolerances.length_eps_mm == 1e-6
    assert tolerances.angle_eps_rad == 1e-9
    assert tolerances.chord_tol_mm == 0.01
    assert dict(tolerances.stage_shares) == {"offset": 0.3, "fitting": 0.2}


@pytest.mark.req("REQ-FND-001")
def test_stage_tol_is_share_of_chord_tolerance() -> None:
    tolerances = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={"offset": 0.3}
    )
    # Compared exactly: chord_tol_mm * share is a single IEEE multiplication, not a sum with
    # rounding, so no tolerance of its own is needed here.
    assert tolerances.stage_tol_mm("offset") == 0.01 * 0.3


@pytest.mark.req("REQ-FND-001")
def test_stage_tol_mm_rejects_an_unknown_stage() -> None:
    tolerances = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={"offset": 0.3}
    )
    with pytest.raises(ValueError, match="unknown stage"):
        tolerances.stage_tol_mm("fitting")


@pytest.mark.req("REQ-FND-001")
def test_stage_shares_is_a_defensive_copy_of_the_caller_dict() -> None:
    shares = {"offset": 0.3}
    tolerances = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares=shares
    )
    shares["offset"] = 0.9
    del shares["offset"]
    assert tolerances.stage_tol_mm("offset") == 0.01 * 0.3


@pytest.mark.req("REQ-FND-007")
def test_stage_shares_cannot_be_written_to() -> None:
    tolerances = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={"offset": 0.3}
    )
    mutable_view = typing.cast("dict[str, float]", tolerances.stage_shares)
    with pytest.raises(TypeError):
        mutable_view["offset"] = 0.9


@pytest.mark.req("REQ-FND-007")
def test_tolerance_set_is_frozen() -> None:
    tolerances = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={"offset": 0.3}
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        tolerances.length_eps_mm = 2e-6  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.req("REQ-FND-007")
def test_tolerance_set_is_hashable_and_equal_sets_hash_equal() -> None:
    first = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={"offset": 0.3}
    )
    second = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={"offset": 0.3}
    )
    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.req("REQ-FND-007")
def test_equality_and_hash_do_not_depend_on_stage_share_insertion_order() -> None:
    first = ToleranceSet(
        length_eps_mm=1e-6,
        angle_eps_rad=1e-9,
        chord_tol_mm=0.01,
        stage_shares={"offset": 0.3, "fitting": 0.2},
    )
    second = ToleranceSet(
        length_eps_mm=1e-6,
        angle_eps_rad=1e-9,
        chord_tol_mm=0.01,
        stage_shares={"fitting": 0.2, "offset": 0.3},
    )
    assert first == second
    assert hash(first) == hash(second)


@pytest.mark.req("REQ-FND-001")
def test_unequal_tolerance_sets_compare_unequal() -> None:
    first = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={"offset": 0.3}
    )
    second = ToleranceSet(
        length_eps_mm=1e-6, angle_eps_rad=1e-9, chord_tol_mm=0.01, stage_shares={"offset": 0.4}
    )
    assert first != second


@pytest.mark.req("REQ-FND-001")
def test_tolerance_set_survives_pickle_round_trip() -> None:
    original = ToleranceSet(
        length_eps_mm=1e-6,
        angle_eps_rad=1e-9,
        chord_tol_mm=0.01,
        stage_shares={"offset": 0.3, "fitting": 0.2},
    )
    restored = pickle.loads(pickle.dumps(original))
    assert restored == original
    assert hash(restored) == hash(original)
    assert dict(restored.stage_shares) == dict(original.stage_shares)


@pytest.mark.req("REQ-FND-001")
def test_tolerance_set_survives_deepcopy() -> None:
    original = ToleranceSet(
        length_eps_mm=1e-6,
        angle_eps_rad=1e-9,
        chord_tol_mm=0.01,
        stage_shares={"offset": 0.3, "fitting": 0.2},
    )
    copied = copy.deepcopy(original)
    assert copied == original
    assert hash(copied) == hash(original)
