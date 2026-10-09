# SPDX-License-Identifier: Apache-2.0
"""Unit tests of `boolean` (plan 0005, step 7): research 02's tests 1, 3, 4, 5 and 15, the Vatti
note's test 7 (overlapping edges of two classes) and the span refusal."""

import dataclasses

import numpy as np
import pytest

from geometry2d_checks import codes
from splintercam.foundation import CANCELLED, CancellationToken, Context
from splintercam.geometry2d import PolygonRegion
from splintercam.offset2d import BooleanOp, EdgeClass, SourceClasses, boolean

Points = list[tuple[float, float]]


def region(*loops: Points, first_id: int = 100) -> PolygonRegion:
    """Loops as a polygon region, each vertex's ID that of the edge starting there."""
    points = np.array([p for loop in loops for p in loop], dtype=np.float64)
    starts = np.cumsum([0] + [len(loop) for loop in loops[:-1]], dtype=np.int64)
    ids = first_id + np.arange(points.shape[0], dtype=np.int64)
    return PolygonRegion(points, starts, ids, np.zeros(points.shape[0], np.uint8))


def square(x0: float, y0: float, x1: float, y1: float) -> Points:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def all_material(*regions: PolygonRegion) -> SourceClasses:
    ids = np.unique(np.concatenate([r.source_ids for r in regions]))
    return SourceClasses(ids, np.full(ids.size, int(EdgeClass.MATERIAL), dtype=np.int8))


def areas(result: PolygonRegion) -> list[float]:
    ends = [*result.loop_starts.tolist()[1:], result.points.shape[0]]
    out: list[float] = []
    for a, b in zip(result.loop_starts.tolist(), ends, strict=True):
        x, y = result.points[a:b, 0], result.points[a:b, 1]
        out.append(0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)))
    return out


def run(a: PolygonRegion, b: PolygonRegion, op: BooleanOp, ctx: Context) -> PolygonRegion:
    result = boolean(a, b, op, all_material(a, b), ctx)
    assert result.value is not None, result.diagnostics
    return result.value


@pytest.mark.req("REQ-OFF-030")
@pytest.mark.parametrize(
    ("op", "area"),
    [(BooleanOp.INTERSECTION, 25.0), (BooleanOp.UNION, 175.0), (BooleanOp.DIFFERENCE, 75.0)],
)
def test_two_squares(op: BooleanOp, area: float, ctx: Context) -> None:
    # Research 02, test 1: A = [0, 10]², B = [5, 15]².
    a, b = region(square(0, 0, 10, 10)), region(square(5, 5, 15, 15), first_id=200)
    assert sum(areas(run(a, b, op, ctx))) == pytest.approx(area, abs=1e-6)


@pytest.mark.req("REQ-OFF-030")
def test_the_positive_rule_keeps_the_counter_clockwise_half_of_a_bow_tie(ctx: Context) -> None:
    # Research 02, test 3: the bow-tie (0, 0), (10, 10), (10, 0), (0, 10) against [-1, 11]².
    bow_tie = region([(0.0, 0.0), (10.0, 10.0), (10.0, 0.0), (0.0, 10.0)])
    frame = region(square(-1, -1, 11, 11), first_id=200)
    result = run(bow_tie, frame, BooleanOp.INTERSECTION, ctx)
    assert sum(areas(result)) == pytest.approx(25.0, abs=1e-6)


@pytest.mark.req("REQ-OFF-030")
def test_a_union_inside_a_notch_adds_nothing(ctx: Context) -> None:
    # Research 02, test 4 (Vatti limit 4): the notched square of area 89 with [1, 3] x [4, 7].
    notched = region([(0, 0), (4, 1), (5, 6), (6, 1), (10, 0), (10, 10), (0, 10)])
    inside = region(square(1, 4, 3, 7), first_id=200)
    result = run(notched, inside, BooleanOp.UNION, ctx)
    assert result.loop_starts.tolist() == [0]
    assert areas(result) == [pytest.approx(89.0, abs=1e-6)]


@pytest.mark.req("REQ-OFF-030")
def test_a_difference_inside_leaves_a_hole(ctx: Context) -> None:
    # Research 02, test 5 (Vatti limit 5): [0, 20]² minus a diamond: area 350, one hole.
    diamond = region([(10.0, 5.0), (15.0, 10.0), (10.0, 15.0), (5.0, 10.0)], first_id=200)
    result = run(region(square(0, 0, 20, 20)), diamond, BooleanOp.DIFFERENCE, ctx)
    assert sorted(areas(result)) == [pytest.approx(-50.0, abs=1e-6), pytest.approx(400.0, abs=1e-6)]


@pytest.mark.req("REQ-OFF-036", "REQ-OFF-030")
def test_squares_touching_at_a_corner_are_split_and_fixed_alike_in_both_orders(
    ctx: Context,
) -> None:
    # Research 02, test 15, first case: [0, 10]² and [10, 20]² touch at (10, 10). Their union is
    # two outer loops, the touching vertex fixed in both, and both input orders give the same
    # arrays bit for bit (DEC-G2D-036): each loop starting at its next vertex, and the operands
    # swapped, change Clipper2's path order.
    a, b = square(0, 0, 10, 10), square(10, 10, 20, 20)
    first = run(region(a), region(b, first_id=200), BooleanOp.UNION, ctx)
    rotated = run(region(a[1:] + a[:1]), region(b[1:] + b[:1], first_id=200), BooleanOp.UNION, ctx)
    swapped = run(region(b, first_id=200), region(a), BooleanOp.UNION, ctx)
    assert first.loop_starts.size == 2
    at_pinch = np.all(first.points == np.array([10.0, 10.0]), axis=1)  # the frame's centre
    assert int(at_pinch.sum()) == 2
    assert first.fixed[at_pinch].tolist() == [1, 1]
    assert int(first.fixed.sum()) == 2
    for other in (rotated, swapped):
        assert first.points.tobytes() == other.points.tobytes()
        assert first.fixed.tobytes() == other.fixed.tobytes()


@pytest.mark.req("REQ-OFF-036", "REQ-OFF-030")
def test_a_hole_touching_the_middle_of_an_outer_edge_is_kept_as_a_hole(ctx: Context) -> None:
    # Research 02, test 15, second case: [0, 20]² minus the triangle (20, 10), (14, 13), (14, 7)
    # (research 02 lists it clockwise; a region's outer loop runs CCW, else the Positive rule cuts
    # nothing). Clipper2 returns the square and a hole whose vertex (20, 10) lies in the middle of
    # the square's right edge, where the square has no vertex: a vertex on another loop's edge,
    # which research 02 (Open items) and the SPEC (Later parts) leave to the arc fit, so it is not
    # a fixed node yet (DEC-OFF-014). Both orders give the same arrays.
    a, b = square(0, 0, 20, 20), [(20.0, 10.0), (14.0, 13.0), (14.0, 7.0)]
    first = run(region(a), region(b, first_id=200), BooleanOp.DIFFERENCE, ctx)
    rotated = run(region(a[1:] + a[:1]), region(b[1:] + b[:1], first_id=200),
                  BooleanOp.DIFFERENCE, ctx)  # fmt: skip
    assert sorted(areas(first)) == [pytest.approx(-18.0, abs=1e-6), pytest.approx(400.0, abs=1e-6)]
    half_unit = ctx.tolerances.grid_unit_mm / 2.0  # back in mm a grid point is centre + k·u
    assert int(np.all(np.abs(first.points - np.array([20.0, 10.0])) < half_unit, axis=1).sum()) == 1
    assert first.points.tobytes() == rotated.points.tobytes()
    assert first.fixed.tobytes() == rotated.fixed.tobytes()


@pytest.mark.req("REQ-OFF-035")
def test_where_a_material_edge_overlaps_an_air_edge_material_wins(ctx: Context) -> None:
    # The Vatti note's test 7: A = [0, 10]² (material) and B = [5, 15] x [0, 10], whose bottom
    # edge (ID 200, air) overlaps A's bottom edge (ID 100) from x = 5 to 10. In the union the
    # overlap carries A's ID; beyond A's end, B's.
    a, b = region(square(0, 0, 10, 10)), region(square(5, 0, 15, 10), first_id=200)
    ids = np.concatenate([a.source_ids, b.source_ids])
    kinds = np.full(ids.size, int(EdgeClass.MATERIAL), dtype=np.int8)
    kinds[ids == 200] = int(EdgeClass.AIR)
    order = np.argsort(ids)
    result = boolean(a, b, BooleanOp.UNION, SourceClasses(ids[order], kinds[order]), ctx).value
    assert result is not None
    starts = result.points
    following = np.roll(starts, -1, axis=0)
    bottom = (starts[:, 1] == 0.0) & (following[:, 1] == 0.0)
    middles = (starts[bottom, 0] + following[bottom, 0]) / 2.0
    for x, source in zip(middles.tolist(), result.source_ids[bottom].tolist(), strict=True):
        assert source == (100 if x < 10.0 else 200)


@pytest.mark.req("REQ-OFF-031")
def test_operands_spanning_the_limit_are_refused(ctx: Context) -> None:
    a, b = region(square(0, 0, 10, 10)), region(square(6702, 0, 6712, 10), first_id=200)
    result = boolean(a, b, BooleanOp.UNION, all_material(a, b), ctx)
    assert result.value is None
    assert codes(result) == ["REGION_TOO_LARGE"]


@pytest.mark.req("REQ-OFF-039")
def test_disjoint_operands_intersect_to_nothing(ctx: Context) -> None:
    a, b = region(square(0, 0, 10, 10)), region(square(20, 0, 30, 10), first_id=200)
    result = boolean(a, b, BooleanOp.INTERSECTION, all_material(a, b), ctx)
    assert result.value is not None
    assert result.value.loop_starts.size == 0
    assert codes(result) == ["OFFSET_EMPTY"]


@pytest.mark.req("REQ-OFF-035")
@pytest.mark.parametrize("lift", [0.4, -0.4])
def test_material_wins_over_air_a_fraction_of_a_grid_unit_apart(lift: float, ctx: Context) -> None:
    # Spec review: two operands may round the same wall to grid points apart; here A's material
    # bottom edge lies 0.4u above or below B's air bottom edge, both rounding to y = 0. The
    # overlap must still take A's ID (D-059), so ties are taken within half the rounding margin,
    # not eps_len (DEC-OFF-014). With eps_len the edge took B's left side (203), not A's.
    u = ctx.tolerances.grid_unit_mm
    a, b = region(square(0, lift * u, 10, 10)), region(square(5, 0, 15, 10), first_id=200)
    ids = np.concatenate([a.source_ids, b.source_ids])
    kinds = np.where(ids == 200, int(EdgeClass.AIR), int(EdgeClass.MATERIAL)).astype(np.int8)
    order = np.argsort(ids)
    result = boolean(a, b, BooleanOp.UNION, SourceClasses(ids[order], kinds[order]), ctx).value
    assert result is not None
    starts, following = result.points, np.roll(result.points, -1, axis=0)
    bottom = (np.abs(starts[:, 1]) < u) & (np.abs(following[:, 1]) < u)
    middles = (starts[bottom, 0] + following[bottom, 0]) / 2.0
    for x, source in zip(middles.tolist(), result.source_ids[bottom].tolist(), strict=True):
        assert source == (100 if x < 10.0 else 200)


@pytest.mark.req("REQ-OFF-036")
def test_a_triangle_touching_the_middle_of_an_edge_unites_alike_in_both_orders(
    ctx: Context,
) -> None:
    # Spec review: research 02's second case of test 15 as a union, where the operand order does
    # change Clipper2's path order: a triangle outside [0, 20]² touching its right edge at
    # (20, 10). Both orders give the same arrays (REQ-OFF-036).
    a, b = square(0, 0, 20, 20), [(20.0, 10.0), (26.0, 7.0), (26.0, 13.0)]
    first = run(region(a), region(b, first_id=200), BooleanOp.UNION, ctx)
    swapped = run(region(b, first_id=200), region(a), BooleanOp.UNION, ctx)
    assert first.points.tobytes() == swapped.points.tobytes()
    assert first.fixed.tobytes() == swapped.fixed.tobytes()
    assert sum(areas(first)) == pytest.approx(418.0, abs=1e-6)


@pytest.mark.req("REQ-OFF-036")
@pytest.mark.xfail(
    strict=True,
    reason="a vertex on another loop's edge is left to the arc fit (DEC-OFF-014, RR-002 item 6)",
)
def test_research_02_test_15_wants_the_touch_in_the_middle_of_an_edge_fixed(ctx: Context) -> None:
    # Research 02, test 15, second case, as written: (20, 10) a fixed node in both loops. Kept as
    # a strict expected failure, so the day the arc fit's rule makes it pass, this test says so.
    a, b = square(0, 0, 20, 20), [(20.0, 10.0), (14.0, 13.0), (14.0, 7.0)]
    result = run(region(a), region(b, first_id=200), BooleanOp.DIFFERENCE, ctx)
    half_unit = ctx.tolerances.grid_unit_mm / 2.0
    at_touch = np.all(np.abs(result.points - np.array([20.0, 10.0])) < half_unit, axis=1)
    assert result.fixed[at_touch].tolist() == [1, 1]


@pytest.mark.req("REQ-OFF-030", "REQ-OFF-039")
@pytest.mark.parametrize(
    ("a_empty", "b_empty", "op", "loops"),
    [
        (False, True, BooleanOp.UNION, 1), (True, False, BooleanOp.UNION, 1),
        (True, True, BooleanOp.UNION, 0), (False, True, BooleanOp.DIFFERENCE, 1),
        (True, False, BooleanOp.DIFFERENCE, 0), (False, True, BooleanOp.INTERSECTION, 0),
    ],
)  # fmt: skip
def test_an_empty_operand(
    a_empty: bool, b_empty: bool, op: BooleanOp, loops: int, ctx: Context
) -> None:
    empty = PolygonRegion(
        np.empty((0, 2)), np.empty(0, np.int64), np.empty(0, np.int64), np.empty(0, np.uint8)
    )
    a = empty if a_empty else region(square(0, 0, 10, 10))
    b = empty if b_empty else region(square(0, 0, 10, 10), first_id=200)
    result = boolean(a, b, op, all_material(a, b), ctx)
    assert result.value is not None
    assert result.value.loop_starts.size == loops
    assert ("OFFSET_EMPTY" in codes(result)) == (loops == 0)


@pytest.mark.req("REQ-OFF-039")
def test_a_square_minus_itself_is_empty(ctx: Context) -> None:
    a, b = region(square(0, 0, 10, 10)), region(square(0, 0, 10, 10), first_id=200)
    result = boolean(a, b, BooleanOp.DIFFERENCE, all_material(a, b), ctx)
    assert codes(result) == ["OFFSET_EMPTY"]


@pytest.mark.req("REQ-OFF-013")
def test_a_bad_operation_or_a_missing_class_is_refused(ctx: Context) -> None:
    a, b = region(square(0, 0, 10, 10)), region(square(5, 5, 15, 15), first_id=200)
    with pytest.raises(ValueError, match="BooleanOp"):
        boolean(a, b, "UNION", all_material(a, b), ctx)  # pyright: ignore[reportArgumentType]
    with pytest.raises(ValueError, match="class"):
        boolean(a, b, BooleanOp.UNION, all_material(a), ctx)


@pytest.mark.req("REQ-OFF-041")
def test_a_cancelled_context_gives_no_region(ctx: Context) -> None:
    cancel = CancellationToken()
    cancel.cancel()
    a, b = region(square(0, 0, 10, 10)), region(square(5, 5, 15, 15), first_id=200)
    result = boolean(
        a, b, BooleanOp.UNION, all_material(a, b), dataclasses.replace(ctx, cancel=cancel)
    )
    assert result.value is None
    assert result.diagnostics == (CANCELLED,)
