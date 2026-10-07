# SPDX-License-Identifier: Apache-2.0
"""Property test: every input loop ends in exactly one place (research 01, Loop tree; SPEC,
Invariants)."""

import math
import re

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from splintercam.foundation import Context
from splintercam.geometry2d import curve_rows
from splintercam.geometry2d._screen import screen_loops

NAN = math.nan
# Squares on a coarse grid, so the same square is drawn twice often; strips of the widths of
# research 01 test 19, so the area tests fire.
SHAPES = st.one_of(
    st.tuples(st.just("square"), st.integers(0, 3), st.integers(0, 3), st.booleans()),
    st.tuples(
        st.just("strip"), st.sampled_from([1e-7, 1e-5, 0.001]), st.integers(0, 3), st.booleans()
    ),
)


def _polygon(shape: tuple[str, float, int, bool]) -> list[tuple[float, float]]:
    kind, a, b, reverse = shape
    if kind == "square":
        x, y = 20.0 * a, 20.0 * b
        points = [(x, y), (x + 10, y), (x + 10, y + 10), (x, y + 10)]
    else:
        y = 20.0 * b + 100.0
        points = [(0.0, y), (10.0, y), (10.0, y + a), (0.0, y + a)]
    return points[::-1] if reverse else points


@pytest.mark.req("REQ-G2D-155", "REQ-G2D-156", "REQ-G2D-157", "REQ-G2D-158", "REQ-G2D-159")
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(shapes=st.lists(SHAPES, min_size=1, max_size=8))
def test_every_input_loop_ends_in_exactly_one_place(
    ctx: Context, shapes: list[tuple[str, float, int, bool]]
) -> None:
    polygons = [_polygon(s) for s in shapes]
    rows = [
        [*p, *q, NAN, NAN, 0.0]
        for points in polygons
        for p, q in zip(points, points[1:] + points[:1], strict=True)
    ]
    starts = np.arange(len(polygons), dtype=np.int64) * 4
    built = curve_rows(np.array(rows), np.arange(len(rows), dtype=np.int64), starts, ctx)
    assert built.value is not None
    result = screen_loops(built.value, ctx)
    assert result.value is not None
    places = [int(i) for i in result.value.kept.tolist()]
    for diagnostic in result.diagnostics:
        numbers = [int(n) for n in re.findall(r"\d+", diagnostic.location or "")]
        if diagnostic.code == "LOOP_DEGENERATE":
            places.append(numbers[0])
        elif diagnostic.code == "LOOP_DUPLICATE":
            places.append(numbers[1])  # "loops i and j": j is removed, i kept
            assert numbers[0] in result.value.kept.tolist()
            assert numbers[0] < numbers[1]
    assert sorted(places) == list(range(len(polygons)))
