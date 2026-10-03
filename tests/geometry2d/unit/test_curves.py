# SPDX-License-Identifier: Apache-2.0
"""Unit tests for lines and arcs: the arc form, its validation and degenerate arcs (research 01,
Curves)."""

import math
from typing import assert_never

import numpy as np
import pytest

from geometry2d_checks import codes, with_length_eps
from splintercam import _kernels
from splintercam.foundation import Context, Severity
from splintercam.geometry2d import Arc, Curve, Line, curve_rows, make_arc, make_line

EPS = 1e-6  # the default length epsilon of the test Context (REQ-FND-008)

NAN = math.nan


def _one_curve(result_value: tuple[Curve, ...] | None) -> Curve:
    assert result_value is not None
    assert len(result_value) == 1
    return result_value[0]


def _describe(curve: Curve) -> str:
    match curve:
        case Line():
            return "line"
        case Arc():
            return "arc"
        case _:
            assert_never(curve)


@pytest.mark.req("REQ-G2D-035")
def test_curve_has_the_variants_line_and_arc() -> None:
    line = Line((0.0, 0.0), (1.0, 0.0))
    arc = Arc((1.0, 0.0), (0.0, 1.0), (0.0, 0.0), math.pi / 2)
    assert [_describe(line), _describe(arc)] == ["line", "arc"]


@pytest.mark.req("REQ-G2D-037")
def test_arc_stores_its_inputs_bit_for_bit(ctx: Context) -> None:
    p0, p1, centre = (10.1, -3.3), (3.3, 10.1 + 2e-15), (0.0, 0.0)
    arc = _one_curve(make_arc(p0, p1, centre, math.pi / 2, ctx).value)
    assert arc == Arc(p0, p1, centre, math.pi / 2)


@pytest.mark.req("REQ-G2D-038")
def test_radius_is_taken_from_p0(ctx: Context) -> None:
    # P1 lies 0.5 eps_len outside the circle through P0: accepted, and r is |P0 - C|.
    result = make_arc((10.0, 0.0), (0.0, 10.0 + 0.5 * EPS), (0.0, 0.0), math.pi / 2, ctx)
    arc = _one_curve(result.value)
    assert isinstance(arc, Arc)
    assert arc.radius_mm == 10.0


@pytest.mark.req("REQ-G2D-040")
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", range(4))
def test_line_with_a_non_finite_value_is_curve_invalid(
    ctx: Context, bad: float, field: int
) -> None:
    values = [0.0, 0.0, 1.0, 1.0]
    values[field] = bad
    result = make_line((values[0], values[1]), (values[2], values[3]), ctx)
    assert result.value is None
    assert codes(result) == ["CURVE_INVALID"]
    assert result.diagnostics[0].severity is Severity.ERROR


@pytest.mark.req("REQ-G2D-040")
def test_finite_line_is_accepted_as_given(ctx: Context) -> None:
    result = make_line((0.0, 0.0), (1.0, 2.0), ctx)
    assert result.ok
    assert result.value == Line((0.0, 0.0), (1.0, 2.0))


@pytest.mark.req("REQ-G2D-040")
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize("field", range(7))
def test_arc_with_a_non_finite_value_is_curve_invalid(ctx: Context, bad: float, field: int) -> None:
    values = [10.0, 0.0, 0.0, 10.0, 0.0, 0.0, math.pi / 2]
    values[field] = bad
    p0, p1, centre = (values[0], values[1]), (values[2], values[3]), (values[4], values[5])
    result = make_arc(p0, p1, centre, values[6], ctx)
    assert result.value is None
    assert codes(result) == ["CURVE_INVALID"]


@pytest.mark.req("REQ-G2D-041")
@pytest.mark.parametrize(
    "sweep", [0.0, -0.0, math.nextafter(math.tau, math.inf), -math.nextafter(math.tau, math.inf)]
)
def test_sweep_zero_or_above_two_pi_is_curve_invalid(ctx: Context, sweep: float) -> None:
    result = make_arc((5.0, 0.0), (5.0, 0.0), (0.0, 0.0), sweep, ctx)
    assert result.value is None
    assert codes(result) == ["CURVE_INVALID"]


@pytest.mark.req("REQ-G2D-042")
@pytest.mark.parametrize(("offset", "accepted"), [(0.9 * EPS, True), (1.1 * EPS, False)])
def test_p1_off_the_circle_beyond_eps_len_is_arc_inconsistent(
    ctx: Context, offset: float, accepted: bool
) -> None:
    result = make_arc((10.0, 0.0), (-(10.0 + offset), 0.0), (0.0, 0.0), math.pi, ctx)
    assert result.ok is accepted
    if not accepted:
        assert codes(result) == ["ARC_INCONSISTENT"]
        assert result.diagnostics[0].severity is Severity.ERROR


@pytest.mark.req("REQ-G2D-043")
@pytest.mark.parametrize(("factor", "accepted"), [(0.9, True), (1.1, False)])
def test_p1_beyond_the_angle_limit_is_arc_inconsistent(
    ctx: Context, factor: float, accepted: bool
) -> None:
    r = 10.0
    angle = math.pi / 2 + factor * EPS / r  # P1 past the end of a quarter arc, on the circle
    p1 = (r * math.cos(angle), r * math.sin(angle))
    result = make_arc((r, 0.0), p1, (0.0, 0.0), math.pi / 2, ctx)
    assert result.ok is accepted
    if not accepted:
        assert codes(result) == ["ARC_INCONSISTENT"]


@pytest.mark.req("REQ-G2D-043")
def test_ccw_quarter_given_a_negative_sweep_is_arc_inconsistent(ctx: Context) -> None:
    result = make_arc((10.0, 0.0), (0.0, 10.0), (0.0, 0.0), -math.pi / 2, ctx)
    assert codes(result) == ["ARC_INCONSISTENT"]


@pytest.mark.req("REQ-G2D-043")
def test_cw_three_quarter_arc_to_the_same_end_is_accepted(ctx: Context) -> None:
    result = make_arc((10.0, 0.0), (0.0, 10.0), (0.0, 0.0), -3 * math.pi / 2, ctx)
    assert result.ok


@pytest.mark.req("REQ-G2D-045")
@pytest.mark.parametrize("sweep", [math.tau, -math.tau])
def test_full_circle_is_accepted(ctx: Context, sweep: float) -> None:
    # Research 01, tests 6 and 20: C = (0, 0), r = 5, P0 = P1 = (5, 0).
    arc = _one_curve(make_arc((5.0, 0.0), (5.0, 0.0), (0.0, 0.0), sweep, ctx).value)
    assert arc == Arc((5.0, 0.0), (5.0, 0.0), (0.0, 0.0), sweep)


@pytest.mark.req("REQ-G2D-047")
def test_arc_with_radius_within_eps_len_becomes_its_chord(ctx: Context) -> None:
    result = make_arc((5e-7, 0.0), (-5e-7, 0.0), (0.0, 0.0), math.pi, ctx)
    assert result.ok
    assert result.value == (Line((5e-7, 0.0), (-5e-7, 0.0)),)


@pytest.mark.req("REQ-G2D-042", "REQ-G2D-047")
def test_a_tiny_circle_with_p1_far_off_it_is_inconsistent(ctx: Context) -> None:
    # DEC-G2D-018: the radial check comes before r <= eps_len, so this is no 100 mm line.
    result = make_arc((5e-7, 0.0), (100.0, 0.0), (0.0, 0.0), math.pi, ctx)
    assert result.value is None
    assert codes(result) == ["ARC_INCONSISTENT"]


@pytest.mark.req("REQ-G2D-042", "REQ-G2D-047")
def test_a_tiny_circle_with_p1_within_eps_len_of_it_is_its_chord(ctx: Context) -> None:
    result = make_arc((5e-7, 0.0), (-1.4e-6, 0.0), (0.0, 0.0), math.pi, ctx)  # 9e-7 off
    assert result.value == (Line((5e-7, 0.0), (-1.4e-6, 0.0)),)


@pytest.mark.req("REQ-G2D-042", "REQ-G2D-047")
@pytest.mark.parametrize(("p1_x", "kept"), [(-1.4e-6, True), (-1.6e-6, False), (1.6e-6, False)])
def test_a_tiny_circle_and_curve_rows_agree_on_the_radial_check(
    ctx: Context, p1_x: float, kept: bool
) -> None:
    # r = 5e-7: P1 0.9e-6 or 1.1e-6 off the circle. make_arc's own check (DEC-G2D-018) and the
    # kernel's check of curve rows must give the same verdict.
    tiny = make_arc((5e-7, 0.0), (p1_x, 0.0), (0.0, 0.0), math.pi, ctx)
    rows = np.array(
        [[5e-7, 0.0, p1_x, 0.0, 0.0, 0.0, math.pi], [p1_x, 0.0, 5e-7, 0.0, NAN, NAN, 0.0]]
    )
    built = curve_rows(rows, np.arange(2, dtype=np.int64), np.zeros(1, np.int64), ctx)
    assert (tiny.value is not None) is kept
    assert ("ARC_INCONSISTENT" in codes(built)) is not kept


@pytest.mark.req("REQ-G2D-048")
def test_closed_arc_with_radius_within_eps_len_is_removed(ctx: Context) -> None:
    result = make_arc((5e-7, 0.0), (5e-7, 0.0), (0.0, 0.0), math.tau, ctx)
    assert result.ok
    assert result.value == ()


@pytest.mark.req("REQ-G2D-003", "REQ-G2D-047")
def test_radius_exactly_eps_len_counts_as_within(ctx: Context) -> None:
    eps = 2.0**-20  # a power of two, so r = |P0 - C| is exactly eps
    result = make_arc((eps, 0.0), (-eps, 0.0), (0.0, 0.0), math.pi, with_length_eps(ctx, eps))
    assert result.value == (Line((eps, 0.0), (-eps, 0.0)),)


@pytest.mark.req("REQ-G2D-049", "REQ-G2D-039")
@pytest.mark.parametrize("sense", [1.0, -1.0])
def test_nearly_closed_arc_becomes_a_full_circle(ctx: Context, sense: float) -> None:
    r, gap = 10.0, 5e-8  # chord and missing arc length 5e-7 mm, both within eps_len
    p1 = (r * math.cos(gap), -sense * r * math.sin(gap))
    result = make_arc((r, 0.0), p1, (0.0, 0.0), sense * (math.tau - gap), ctx)
    assert result.ok
    assert result.value == (Arc((r, 0.0), (r, 0.0), (0.0, 0.0), sense * math.tau),)


@pytest.mark.req("REQ-G2D-049")
def test_nearly_closed_rule_needs_a_sweep_above_pi(ctx: Context) -> None:
    # A tiny arc with P1 within eps_len of P0 stays an arc: its sweep is small, not near 2*pi.
    r, sweep = 10.0, 5e-8
    result = make_arc((r, 0.0), (r * math.cos(sweep), r * math.sin(sweep)), (0.0, 0.0), sweep, ctx)
    arc = _one_curve(result.value)
    assert isinstance(arc, Arc)
    assert arc.sweep_rad == sweep


@pytest.mark.req("REQ-G2D-025", "REQ-G2D-042")
def test_length_eps_comes_from_the_context(ctx: Context) -> None:
    p0, p1, centre = (10.0, 0.0), (-(10.0 + 1.5e-6), 0.0), (0.0, 0.0)
    assert codes(make_arc(p0, p1, centre, math.pi, ctx)) == ["ARC_INCONSISTENT"]
    assert make_arc(p0, p1, centre, math.pi, with_length_eps(ctx, 2e-6)).ok


def _check_arcs(rows: list[list[float]], length_eps_mm: float) -> list[int]:
    out = np.empty(len(rows), dtype=np.int8)
    _kernels.geometry2d.check_arcs(np.array(rows, dtype=np.float64), length_eps_mm, out)
    return out.tolist()


@pytest.mark.req("REQ-G2D-003", "REQ-G2D-042")
def test_p1_exactly_eps_len_off_the_circle_counts_as_within() -> None:
    # Powers of two: |P1 - C| - r = (1 + 2^-20) - 1 = 2^-20 exactly.
    eps = 2.0**-20
    beyond = math.nextafter(1.0 + eps, math.inf)
    rows = [
        [1.0, 0.0, -(1.0 + eps), 0.0, 0.0, 0.0, math.pi],
        [1.0, 0.0, -beyond, 0.0, 0.0, 0.0, math.pi],
    ]
    assert _check_arcs(rows, eps) == [0, 1]


@pytest.mark.req("REQ-G2D-003", "REQ-G2D-043")
def test_sweep_exactly_at_the_angle_limit_counts_as_within() -> None:
    # P1 = (0, 1) gives the angle pi/2 exactly (x = 0); with r = 1 the difference is
    # sweep - pi/2, exact by Sterbenz's lemma, so a length epsilon equal to it sits on the limit.
    sweep = math.pi / 2 + 2.0**-20
    limit = sweep - math.pi / 2
    row = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0, sweep]
    assert _check_arcs([row], limit) == [0]
    assert _check_arcs([row], math.nextafter(limit, 0.0)) == [2]


@pytest.mark.req("REQ-G2D-043", "REQ-G2D-045")
@pytest.mark.parametrize("sweep", [math.tau, -math.tau])
def test_full_circle_row_passes_the_kernel_angle_check(sweep: float) -> None:
    # The angle from P0 to P1 = P0 is 0, which matches |sweep| = 2*pi modulo 2*pi.
    assert _check_arcs([[5.0, 0.0, 5.0, 0.0, 0.0, 0.0, sweep]], EPS) == [0]


@pytest.mark.req("REQ-G2D-043")
def test_line_rows_are_not_checked() -> None:
    assert _check_arcs([[0.0, 0.0, 1.0, 0.0, math.nan, math.nan, 0.0]], EPS) == [0]
