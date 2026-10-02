# SPDX-License-Identifier: Apache-2.0
"""Unit tests for bounding boxes of lines and arcs (research 01, Helpers; test 18)."""

import math

import pytest

from splintercam.foundation import Context
from splintercam.geometry2d import Arc, Box, Line, bounding_box


@pytest.mark.req("REQ-G2D-213")
def test_line_box_is_the_box_of_its_end_points(ctx: Context) -> None:
    assert bounding_box(Line((3.0, -1.0), (-2.0, 4.0)), ctx) == Box(-2.0, -1.0, 3.0, 4.0)


def _point(angle: float) -> tuple[float, float]:
    # Points on the unit circle about (1, 2), exact on the axes.
    exact = {0.0: (2.0, 2.0), 0.5: (1.0, 3.0), 1.0: (0.0, 2.0), 1.5: (1.0, 1.0)}
    if angle in exact:
        return exact[angle]
    return (1.0 + math.cos(angle * math.pi), 2.0 + math.sin(angle * math.pi))


@pytest.mark.req("REQ-G2D-214")
@pytest.mark.parametrize(
    ("start", "end", "sweep", "box"),
    [
        (
            0.25,
            0.75,
            0.5,
            (1.0 + math.cos(0.75 * math.pi), None, 1.0 + math.cos(0.25 * math.pi), 3.0),
        ),
        (1.75, 0.25, 0.5, (None, None, 2.0, None)),  # crosses 0
        (0.75, 1.25, 0.5, (0.0, None, None, None)),  # crosses pi
        (1.25, 1.75, 0.5, (None, 1.0, None, None)),  # crosses 3*pi/2
        (0.1, 0.4, 0.3, (None, None, None, None)),  # crosses none
        (0.25, 0.75, -1.5, (0.0, 1.0, 2.0, None)),  # CW the long way: crosses 0, 3*pi/2, pi
        (0.0, 0.5, 0.5, (None, None, 2.0, 3.0)),  # starts and ends on the axes
    ],
)
def test_arc_box_includes_the_axis_points_in_its_sweep(
    ctx: Context,
    start: float,
    end: float,
    sweep: float,
    box: tuple[float | None, float | None, float | None, float | None],
) -> None:
    p0, p1 = _point(start), _point(end)
    expected = [
        min(p0[0], p1[0]),
        min(p0[1], p1[1]),
        max(p0[0], p1[0]),
        max(p0[1], p1[1]),
    ]
    expected = [
        value if value is not None else default
        for value, default in zip(box, expected, strict=True)
    ]
    got = bounding_box(Arc(p0, p1, (1.0, 2.0), sweep * math.pi), ctx)
    assert (got.x_min_mm, got.y_min_mm, got.x_max_mm, got.y_max_mm) == pytest.approx(
        expected, abs=1e-15
    )


@pytest.mark.req("REQ-G2D-214")
@pytest.mark.parametrize("sweep", [math.tau, -math.tau])
def test_full_circle_box_has_all_four_axis_points(ctx: Context, sweep: float) -> None:
    assert bounding_box(Arc((6.0, 2.0), (6.0, 2.0), (1.0, 2.0), sweep), ctx) == Box(
        -4.0, -3.0, 6.0, 7.0
    )
