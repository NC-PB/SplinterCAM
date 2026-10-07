# SPDX-License-Identifier: Apache-2.0
"""Unit tests for polygon regions at the kernel boundary (research 01, Kernel arrays)."""

import math

import numpy as np
import pytest
from numpy.typing import NDArray

from geometry2d_checks import codes
from splintercam.foundation import Context
from splintercam.geometry2d import polygon_region

Valid = tuple[NDArray[np.float64], NDArray[np.int64], NDArray[np.int64], NDArray[np.uint8]]


def _valid() -> Valid:
    """A square and a triangle, the triangle's apex a fixed node."""
    points = np.array(
        [(0, 0), (10, 0), (10, 10), (0, 10), (2, 2), (4, 2), (3, 4)], dtype=np.float64
    )
    starts = np.array([0, 4], dtype=np.int64)
    ids = np.array([1, 2, 3, 4, 5, 6, 7], dtype=np.int64)
    fixed = np.array([0, 0, 0, 0, 0, 0, 1], dtype=np.uint8)
    return points, starts, ids, fixed


@pytest.mark.req("REQ-G2D-183", "REQ-G2D-201")
def test_valid_region_is_kept_as_read_only_copies(ctx: Context) -> None:
    points, starts, ids, fixed = _valid()
    result = polygon_region(points, starts, ids, fixed, ctx)
    assert result.ok, result.diagnostics
    region = result.value
    assert region is not None
    np.testing.assert_array_equal(region.points, points)
    assert region.loop_starts.tolist() == [0, 4]
    assert region.source_ids.tolist() == ids.tolist()
    assert region.fixed.tolist() == fixed.tolist()
    for array in (region.points, region.loop_starts, region.source_ids, region.fixed):
        assert not array.flags.writeable
        assert array.flags.c_contiguous
    points[0, 0] = 99.0
    assert region.points[0, 0] == 0.0  # a copy, not a view of the caller's array


@pytest.mark.req("REQ-G2D-187")
def test_empty_region_is_valid(ctx: Context) -> None:
    result = polygon_region(
        np.empty((0, 2)), np.empty(0, np.int64), np.empty(0, np.int64), np.empty(0, np.uint8), ctx
    )
    assert result.ok, result.diagnostics
    assert result.value is not None
    assert result.value.loop_starts.size == 0


Arrays = tuple[NDArray[np.generic], NDArray[np.generic], NDArray[np.generic], NDArray[np.generic]]


def _rejected(ctx: Context, arrays: Arrays) -> None:
    result = polygon_region(*arrays, ctx)
    assert result.value is None
    assert codes(result) == ["REGION_INVALID"]


@pytest.mark.req("REQ-G2D-183", "REQ-G2D-187")
@pytest.mark.parametrize(
    "broken",
    [
        "points_dtype",
        "points_shape",
        "starts_dtype",
        "ids_dtype",
        "ids_length",
        "fixed_dtype",
        "fixed_length",
        "fixed_value",
    ],
)
def test_wrong_shapes_dtypes_and_flags_are_region_invalid(ctx: Context, broken: str) -> None:
    points, starts, ids, fixed = _valid()
    arrays: list[NDArray[np.generic]] = [points, starts, ids, fixed]
    match broken:
        case "points_dtype":
            arrays[0] = points.astype(np.float32)
        case "points_shape":
            arrays[0] = np.hstack([points, points[:, :1]])
        case "starts_dtype":
            arrays[1] = starts.astype(np.int32)
        case "ids_dtype":
            arrays[2] = ids.astype(np.float64)
        case "ids_length":
            arrays[2] = ids[:-1]
        case "fixed_dtype":
            arrays[3] = fixed.astype(np.int64)
        case "fixed_length":
            arrays[3] = fixed[:-1]
        case _:
            fixed[2] = 2
    _rejected(ctx, (arrays[0], arrays[1], arrays[2], arrays[3]))


@pytest.mark.req("REQ-G2D-184", "REQ-G2D-187")
@pytest.mark.parametrize("starts", [[1, 4], [0, 4, 4], [0, 5, 4], [0, 7]])
def test_loop_starts_must_start_at_0_and_ascend(ctx: Context, starts: list[int]) -> None:
    points, _, ids, fixed = _valid()
    _rejected(ctx, (points, np.array(starts, dtype=np.int64), ids, fixed))


@pytest.mark.req("REQ-G2D-185", "REQ-G2D-187")
def test_a_loop_repeating_its_first_vertex_is_region_invalid(ctx: Context) -> None:
    points, starts, ids, fixed = _valid()
    points[3] = points[0]  # the square's last vertex repeats its first
    _rejected(ctx, (points, starts, ids, fixed))


@pytest.mark.req("REQ-G2D-186", "REQ-G2D-187")
def test_a_loop_of_two_vertices_is_region_invalid(ctx: Context) -> None:
    points, _, ids, fixed = _valid()
    _rejected(ctx, (points, np.array([0, 2], dtype=np.int64), ids, fixed))


@pytest.mark.req("REQ-G2D-187")
@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_a_non_finite_point_is_region_invalid(ctx: Context, value: float) -> None:
    points, starts, ids, fixed = _valid()
    points[5, 1] = value
    _rejected(ctx, (points, starts, ids, fixed))


@pytest.mark.req("REQ-G2D-201")
def test_a_strided_view_gives_the_result_of_its_copy(ctx: Context) -> None:
    points, starts, ids, fixed = _valid()
    wide = np.repeat(points, 2, axis=1)[:, ::2]  # a non-contiguous view of the same values
    assert not wide.flags.c_contiguous
    region = polygon_region(wide, starts, ids, fixed, ctx).value
    assert region is not None
    np.testing.assert_array_equal(region.points, points)
    assert region.points.flags.c_contiguous
    assert not np.shares_memory(region.points, wide)


@pytest.mark.req("REQ-G2D-184", "REQ-G2D-187")
def test_points_without_loops_are_region_invalid(ctx: Context) -> None:
    points, _, ids, fixed = _valid()
    _rejected(ctx, (points, np.empty(0, np.int64), ids, fixed))
