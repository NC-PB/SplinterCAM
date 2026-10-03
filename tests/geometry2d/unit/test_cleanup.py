# SPDX-License-Identifier: Apache-2.0
"""Unit tests for polyline cleanup (research 01, Helpers; test 12)."""

import math

import numpy as np
import pytest

import geometry2d_oracles as oracle
from geometry2d_checks import codes, with_length_eps
from splintercam.foundation import Context, Severity
from splintercam.geometry2d import cleanup


def _kept(points: list[tuple[float, float]], ctx: Context) -> list[int]:
    result = cleanup(np.array(points), ctx)
    assert result.value is not None
    return result.value.tolist()


@pytest.mark.req("REQ-G2D-207", "REQ-G2D-020")
def test_research_test_12_collinear_vertex(ctx: Context) -> None:
    # (5, 0) lies exactly on the line (0, 0)-(10, 0) between them; one rounding unit off it stays.
    square = [(0.0, 0.0), (5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert _kept(square, ctx) == [0, 2, 3, 4]
    off = [(0.0, 0.0), (5.0, 2.0**-50), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert _kept(off, ctx) == [0, 1, 2, 3, 4]


@pytest.mark.req("REQ-G2D-204", "REQ-G2D-206")
def test_research_test_12_nine_vertices_become_five_runs(ctx: Context) -> None:
    # Nine vertices 0.9e-6 mm apart on a convex curve (off a line, so no collinear drop): runs
    # start at 0, 1.8e-6, 3.6e-6, 5.4e-6 and 7.2e-6 mm.
    nine = [(0.9e-6 * k, 1e-10 * k * k) for k in range(9)]
    points = [*nine, (1.0, 1.0), (0.0, 1.0)]
    kept = _kept(points, ctx)
    assert kept == [0, 2, 4, 6, 8, 9, 10]
    eps = ctx.tolerances.length_eps_mm
    for i, p in enumerate(points):  # every vertex stays within eps_len of the vertex it joined
        start = max(k for k in kept if k <= i)
        assert math.dist(p, points[start]) <= eps


@pytest.mark.req("REQ-G2D-209", "REQ-G2D-211")
def test_research_test_12_spike(ctx: Context) -> None:
    loop = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (10.0, 20.0), (10.0, 10.0), (0.0, 10.0)]
    result = cleanup(np.array(loop), ctx)
    assert result.value is not None
    kept = result.value.tolist()
    # The collinear pass, first in the fixed order, drops (10, 10) at 2, between (10, 0) and the
    # tip; the spike pass then drops the tip; the (10, 10) at 4 stays.
    assert kept == [0, 1, 4, 5]
    assert codes(result) == ["CLEANUP_SPIKE"]
    assert result.diagnostics[0].severity is Severity.INFO
    assert oracle.polygon_area([loop[i] for i in kept]) == oracle.polygon_area(loop)


@pytest.mark.req("REQ-G2D-209")
def test_one_diagnostic_per_spike(ctx: Context) -> None:
    # Two spikes: up from (5, 0) and left from (0, 5).
    loop = [
        (0.0, 0.0),
        (5.0, 0.0),
        (5.0, -3.0),
        (5.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (0.0, 5.0),
        (-4.0, 5.0),
        (0.0, 5.0),
    ]
    result = cleanup(np.array(loop), ctx)
    assert codes(result) == ["CLEANUP_SPIKE", "CLEANUP_SPIKE"]
    assert result.value is not None
    assert [loop[i] for i in result.value.tolist()] == [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
    ]


@pytest.mark.req("REQ-G2D-205")
def test_a_last_run_near_the_first_vertex_joins_it(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    loop = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0), (0.5 * eps, 0.5 * eps)]
    assert _kept(loop, ctx) == [0, 1, 2, 3]
    # One vertex of the last run farther than eps_len from the first: the run stays.
    loop = [
        (0.0, 0.0),
        (10.0, 0.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (-1.5 * eps, 0.1 * eps),
        (-0.9 * eps, 0.0),
    ]
    assert _kept(loop, ctx) == [0, 1, 2, 3, 4]


@pytest.mark.req("REQ-G2D-212")
def test_the_passes_repeat_until_nothing_changes(ctx: Context) -> None:
    # Dropping the spike leaves two equal neighbours, which the next merge pass joins; then
    # (5, 0) is collinear between them.
    loop = [(0.0, 0.0), (5.0, 0.0), (5.0, 7.0), (5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    result = cleanup(np.array(loop), ctx)
    assert result.value is not None
    kept: list[int] = result.value.tolist()
    assert codes(result) == ["CLEANUP_SPIKE"]
    assert [loop[i] for i in kept] == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    again = _kept([loop[i] for i in kept], ctx)
    assert again == list(range(len(kept)))


@pytest.mark.req("REQ-G2D-204")
def test_a_merge_may_leave_fewer_than_three_vertices(ctx: Context) -> None:
    result = cleanup(np.array([(0.0, 0.0), (1e-7, 0.0), (5.0, 0.0)]), ctx)
    assert result.value is not None
    assert result.value.tolist() == [0, 2]
    assert codes(result) == []


@pytest.mark.req("REQ-G2D-201")
def test_the_indices_are_int64_read_only_and_non_finite_input_is_refused(ctx: Context) -> None:
    result = cleanup(np.array([(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]), ctx)
    assert result.value is not None
    assert result.value.dtype == np.int64
    assert not result.value.flags.writeable
    for bad in (math.inf, math.nan):
        with pytest.raises(ValueError, match="finite"):
            cleanup(np.array([(0.0, 0.0), (bad, 0.0), (0.0, 1.0)]), ctx)


@pytest.mark.req("REQ-G2D-231")
def test_cleanup_is_bit_identical_when_repeated(ctx: Context) -> None:
    points = np.random.default_rng(5).uniform(-1e-6, 1e-6, size=(200, 2)) + np.repeat(
        np.random.default_rng(6).uniform(-10, 10, size=(40, 2)), 5, axis=0
    )
    first, second = cleanup(points, ctx), cleanup(points, ctx)
    assert first.value is not None
    assert second.value is not None
    assert first.value.tobytes() == second.value.tobytes()
    assert first.diagnostics == second.diagnostics


@pytest.mark.req("REQ-G2D-020")
def test_vertices_merge_before_the_exact_tests(ctx: Context) -> None:
    # (5, 0) and (5 + eps/2, 0) merge first; tested before the merge, (5, 0) would lie strictly
    # between (0, 0) and (5 + eps/2, 0) and be dropped instead.
    eps = ctx.tolerances.length_eps_mm
    loop = [(0.0, 0.0), (5.0, 0.0), (5.0 + 0.5 * eps, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert _kept(loop, ctx) == [0, 1, 3, 4]


@pytest.mark.req("REQ-G2D-205", "REQ-G2D-206")
def test_a_last_run_whose_later_vertex_lies_beyond_stays(ctx: Context) -> None:
    # Spec review of step 9: the far vertex second in the last run. A later round must not join
    # the run's first vertex alone, which would leave (-1.5 eps, 0.1 eps) 1.5 eps from vertex 0.
    eps = ctx.tolerances.length_eps_mm
    loop = [
        (0.0, 0.0),
        (10.0, 1.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (-0.9 * eps, 0.0),
        (-1.5 * eps, 0.1 * eps),
    ]
    assert _kept(loop, ctx) == [0, 1, 2, 3, 4]
    loop = [
        (0.0, 0.0),
        (10.0, 1.0),
        (10.0, 10.0),
        (0.0, 10.0),
        (-0.9 * eps, 0.0),
        (-1.6 * eps, 0.3 * eps),
    ]
    assert _kept(loop, ctx) == [0, 1, 2, 3, 4]


@pytest.mark.req("REQ-G2D-206", "REQ-G2D-212")
def test_a_later_round_moves_no_vertex_twice(ctx: Context) -> None:
    # Spec review of step 9: (0.9 eps, 0.9 eps) merges into (0.9 eps, 0); after the spike at
    # (10, 0) goes, (0.9 eps, 0) lies within eps_len of (0, 0), but its merged vertex does not.
    eps = ctx.tolerances.length_eps_mm
    loop = [
        (0.0, 0.0),
        (10.0, 0.0),
        (0.9 * eps, 0.0),
        (0.9 * eps, 0.9 * eps),
        (0.0, 10.0),
        (-10.0, 1.0),
    ]
    result = cleanup(np.array(loop), ctx)
    assert result.value is not None
    assert result.value.tolist() == [0, 2, 4, 5]
    assert codes(result) == ["CLEANUP_SPIKE"]


@pytest.mark.req("REQ-G2D-207", "REQ-G2D-209")
def test_the_drop_passes_stop_at_three_vertices(ctx: Context) -> None:
    # (ours) A loop that would lose more encloses nothing; the area test reports it.
    result = cleanup(np.array([(0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0)]), ctx)
    assert result.value is not None
    assert len(result.value) == 3


@pytest.mark.req("REQ-G2D-204")
def test_eps_len_itself_merges(ctx: Context) -> None:
    eps = ctx.tolerances.length_eps_mm
    beyond = math.nextafter(eps, math.inf)
    assert _kept([(0.0, 0.0), (eps, 0.0), (10.0, 0.0), (0.0, 10.0)], ctx) == [0, 2, 3]
    assert _kept([(0.0, 0.0), (beyond, 1e-9), (10.0, 0.0), (0.0, 10.0)], ctx) == [0, 1, 2, 3]


@pytest.mark.req("REQ-G2D-025")
def test_eps_len_comes_from_the_context(ctx: Context) -> None:
    loop = [(0.0, 0.0), (5e-6, 1e-7), (10.0, 0.0), (0.0, 10.0)]
    assert _kept(loop, ctx) == [0, 1, 2, 3]
    assert _kept(loop, with_length_eps(ctx, 1e-5)) == [0, 2, 3]
