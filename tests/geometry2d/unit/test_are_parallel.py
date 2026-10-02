# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the parallel test (research 01, Tolerances; test 22)."""

import math

import numpy as np
import pytest

from splintercam.foundation import Context
from splintercam.geometry2d import are_parallel


def _direction(angle: float, length: float = 1.0) -> list[float]:
    return [length * math.cos(angle), length * math.sin(angle)]


@pytest.mark.req("REQ-G2D-027")
def test_directions_1e_10_apart_are_parallel_and_1e_8_apart_are_not(ctx: Context) -> None:
    # Research 01, test 22, with eps_ang = 1e-9 rad; one batch, rows of different lengths.
    a = np.array([_direction(0.3), _direction(0.3, 50.0)])
    b = np.array([_direction(0.3 + 1e-10, 7.0), _direction(0.3 + 1e-8)])
    assert are_parallel(a, b, ctx).tolist() == [True, False]


@pytest.mark.req("REQ-G2D-027")
def test_opposite_directions_and_a_zero_vector_count_as_parallel(ctx: Context) -> None:
    a = np.array([[1.0, 2.0], [0.0, 0.0]])
    b = np.array([[-2.0, -4.0], [3.0, 1.0]])
    assert are_parallel(a, b, ctx).tolist() == [True, True]


@pytest.mark.req("REQ-G2D-027")
def test_result_is_one_bool_per_row(ctx: Context) -> None:
    result = are_parallel(np.zeros((3, 2)), np.ones((3, 2)), ctx)
    assert result.dtype == np.bool_
    assert result.shape == (3,)
