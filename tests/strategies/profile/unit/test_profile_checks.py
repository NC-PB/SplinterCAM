# SPDX-License-Identifier: Apache-2.0
"""Unit tests for what the profile refuses before and at the offset: the declarations, the
preconditions, the nine value checks, the region check and cancellation (REQ-PRF-001 to 010, 020,
021; research 22, Parameters, Traps and tests 3 and 4)."""

import dataclasses
import math

import numpy as np
import pytest

from geometry2d_checks import codes, polygon
from model_jobs import example_job
from profile_checks import STOCK, make_context, operation, task, with_stock
from splintercam.cl import ClOperation
from splintercam.foundation import CANCELLED, Context, Result, Severity
from splintercam.geometry2d import CurveRows, PolygonRegion
from splintercam.model import FlatEndMill, StockBox, Unit, check_job
from splintercam.offset2d import offset_region
from splintercam.strategies.profile import DECLARATIONS, STRATEGY_ID, ProfileInput, plan_profile

AT = "operation (PROFILE_1)"
_OFFSET = "splintercam.strategies.profile._plan.offset_region"  # patched to watch the offset


def _refused(result: Result[ClOperation], code: str) -> str:
    # The one diagnostic `code`, an error at the operation; its message.
    assert result.value is None
    found = [d for d in result.diagnostics if d.code == code]
    assert len(found) == 1, codes(result)
    assert found[0].severity is Severity.ERROR
    assert found[0].location == AT
    return found[0].message


def _plan(ctx: Context, **changed: object) -> Result[ClOperation]:
    return plan_profile(task(ctx, **changed), ctx)  # type: ignore[arg-type]


@pytest.mark.req("REQ-PRF-001")
def test_the_declarations_in_order_with_units_defaults_and_ranges() -> None:
    inf = math.inf
    expected = [
        ("allowance_mm", Unit.MM, 0.0, -inf, True),
        ("z_top_mm", Unit.MM, None, -inf, True),
        ("z_bottom_mm", Unit.MM, None, -inf, True),
        ("stepdown_mm", Unit.MM, None, 0.0, True),
        ("cut_feed_mm_per_min", Unit.MM_PER_MIN, None, 0.0, True),
        ("plunge_feed_mm_per_min", Unit.MM_PER_MIN, None, 0.0, True),
        ("air_gap_ratio", Unit.RATIO, 0.2, 0.0, True),
    ]
    got = [(d.name, d.unit, d.default, d.low, d.low_open) for d in DECLARATIONS]
    assert got == expected
    assert all(d.high == inf and d.high_open and d.source for d in DECLARATIONS)
    assert STRATEGY_ID == "profile"


@pytest.mark.req("REQ-PRF-001")
def test_check_job_accepts_the_example_job_with_the_declarations() -> None:
    ctx = make_context()
    given = tuple((n, v) for n, v in operation().parameters if n != "air_gap_ratio")
    op = dataclasses.replace(operation(), parameters=given)
    checked = check_job(example_job((op,)), {STRATEGY_ID: DECLARATIONS}, ctx)
    assert checked.ok, codes(checked)
    assert checked.value is not None
    assert checked.value.setup.operations[0] == operation()  # air gap ratio completed to 0.2


def _broken(ctx: Context, case: str) -> tuple[ProfileInput, Context]:
    good = task(ctx)
    op, params = good.operation, good.operation.parameters
    shifted = good.contour.rows + np.array([200.0, 0.0, 200.0, 0.0, 200.0, 0.0, 0.0])
    two_loops = CurveRows(
        np.concatenate([good.contour.rows, shifted]),
        np.concatenate([good.contour.ids, good.contour.ids + 8]),
        np.array([0, 8], dtype=np.int64),
    )
    changed = {
        "strategy": dataclasses.replace(op, strategy="pocket"),
        "missing": dataclasses.replace(op, parameters=params[:-1]),
        "order": dataclasses.replace(op, parameters=(params[1], params[0], *params[2:])),
        "point": dataclasses.replace(op, point_number=2),
    }
    if case in changed:
        return dataclasses.replace(good, operation=changed[case]), ctx
    if case == "tool":
        return dataclasses.replace(good, tool=FlatEndMill(2, 10.0, 30.0)), ctx
    if case == "loops":
        return dataclasses.replace(good, contour=two_loops), ctx
    return good, make_context(0.02)  # a context of another tol


@pytest.mark.req("REQ-PRF-002")
@pytest.mark.parametrize(
    ("case", "named"),
    [("strategy", "strategy 'pocket'"), ("missing", "parameters"), ("order", "parameters"),
     ("point", "no point 2"), ("tool", "tool 2"), ("loops", "one loop"), ("tol", "tolerance")],
)  # fmt: skip
def test_a_broken_precondition_raises_naming_it(case: str, named: str) -> None:
    given, context = _broken(make_context(), case)
    with pytest.raises(ValueError, match="PROFILE_1") as raised:
        plan_profile(given, context)
    assert named in str(raised.value)


@pytest.mark.req("REQ-PRF-003")
def test_research_22_test_3_an_allowance_of_minus_r_is_refused() -> None:
    message = _refused(_plan(make_context(), allowance_mm=-5.0), "PROFILE_ALLOWANCE")
    assert "-5.0" in message
    assert _plan(make_context(), allowance_mm=-4.9).ok


@pytest.mark.req("REQ-PRF-004")
@pytest.mark.parametrize("z_bottom", [0.0, 1.0])
def test_a_bottom_not_below_the_top_is_refused(z_bottom: float) -> None:
    result = _plan(make_context(), z_bottom_mm=z_bottom)
    message = _refused(result, "PROFILE_DEPTH_INVALID")
    assert f"{z_bottom!r}" in message
    assert "PROFILE_TOP_TOO_HIGH" not in codes(result)  # REQ-PRF-020: no levels to check


@pytest.mark.req("REQ-PRF-005")
def test_a_first_level_at_h_r_is_refused() -> None:
    # z_top 7, z_bottom -1, step 4: z_1 = 3 = h_r (stock top 0).
    message = _refused(
        _plan(make_context(), z_top_mm=7.0, z_bottom_mm=-1.0), "PROFILE_TOP_TOO_HIGH"
    )
    assert "3.0" in message


@pytest.mark.req("REQ-PRF-005")
def test_a_stock_top_where_h_r_rounds_to_h_c_is_refused() -> None:
    result = _plan(make_context(), stock=with_stock(STOCK, z1=1e16))
    _refused(result, "PROFILE_TOP_TOO_HIGH")


@pytest.mark.req("REQ-PRF-005")
def test_a_first_pass_deeper_than_the_step_down_below_the_stock_top_is_refused() -> None:
    result = _plan(make_context(), stock=with_stock(STOCK, z1=0.5), stepdown_mm=1.0)
    message = _refused(result, "PROFILE_FIRST_PASS_DEEP")
    assert "1.5" in message
    assert codes(result) == ["PROFILE_FIRST_PASS_DEEP"]


@pytest.mark.req("REQ-PRF-005")
def test_a_top_above_the_stock_top_is_accepted() -> None:
    assert _plan(make_context(), z_top_mm=1.0).ok


@pytest.mark.req("REQ-PRF-006")
def test_a_bottom_below_the_stock_bottom_is_refused() -> None:
    message = _refused(_plan(make_context(), z_bottom_mm=-20.001), "PROFILE_BELOW_STOCK")
    assert "-20.001" in message
    assert _plan(make_context(), z_bottom_mm=-20.0).ok


@pytest.mark.req("REQ-PRF-007")
def test_research_22_test_4_deeper_than_the_flute_length_is_refused() -> None:
    deep = with_stock(STOCK, z0=-40.0)
    message = _refused(_plan(make_context(), stock=deep, z_bottom_mm=-30.001), "PROFILE_TOO_DEEP")
    assert "30.001" in message
    assert "30.0" in message
    assert _plan(make_context(), stock=deep, z_bottom_mm=-30.0).ok


@pytest.mark.req("REQ-PRF-007")
def test_the_depth_is_measured_from_the_stock_top_not_from_z_top() -> None:
    # z_top -5 to z_bottom -31: 26 mm of cut, but 31 mm below the stock top.
    deep = with_stock(STOCK, z0=-40.0)
    result = _plan(make_context(), stock=deep, z_top_mm=-25.0, z_bottom_mm=-31.0, stepdown_mm=30.0)
    _refused(result, "PROFILE_TOO_DEEP")


@pytest.mark.req("REQ-PRF-008")
def test_a_step_down_above_the_flute_length_is_refused() -> None:
    assert _plan(make_context(), stepdown_mm=30.0).ok
    _refused(_plan(make_context(), stepdown_mm=30.001), "PROFILE_STEP_DOWN")


@pytest.mark.req("REQ-PRF-009")
@pytest.mark.parametrize(
    ("corner", "value", "side"),
    [("x0", 0.001, "x min"), ("y0", 0.001, "y min"), ("x1", 99.999, "x max"),
     ("y1", 59.999, "y max")],
)  # fmt: skip
def test_a_part_past_a_side_of_the_stock_is_refused(corner: str, value: float, side: str) -> None:
    message = _refused(_plan(make_context(), stock=with_stock(STOCK, **{corner: value})),
                       "PROFILE_STOCK_SMALL")  # fmt: skip
    assert side in message


@pytest.mark.req("REQ-PRF-009")
def test_a_part_touching_the_stock_is_accepted() -> None:
    flush = with_stock(STOCK, x0=0.0, y0=0.0, x1=100.0, y1=60.0)
    assert _plan(make_context(), stock=flush).ok


@pytest.mark.req("REQ-PRF-009")
def test_an_air_gap_not_above_eps_len_is_refused() -> None:
    _refused(_plan(make_context(), air_gap_ratio=1e-7), "PROFILE_AIR_GAP")


@pytest.mark.req("REQ-PRF-010")
def test_research_22_test_1_gives_one_loop() -> None:
    result = _plan(make_context())
    assert result.ok, codes(result)
    assert codes(result) == []


@pytest.mark.req("REQ-PRF-010")
def test_a_c_shape_closing_round_a_hole_is_refused_with_its_loop_count() -> None:
    ctx = make_context()
    c_shape = polygon([(0, 0), (60, 0), (60, 27), (45, 27), (45, 15), (15, 15), (15, 45),
                       (45, 45), (45, 33), (60, 33), (60, 60), (0, 60)], ctx)  # fmt: skip
    stock = with_stock(STOCK, x1=65.0, y1=65.0)
    message = _refused(plan_profile(task(ctx, contour=c_shape, stock=stock), ctx), "PROFILE_REGION")
    assert "2" in message


@pytest.mark.req("REQ-PRF-010", "REQ-PRF-021")
def test_offset2d_cancelled_gives_cancelled_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_context()

    def cancelling(*args: object) -> Result[PolygonRegion]:
        ctx.cancel.cancel()  # offset2d sees it at its entry and returns no value
        return offset_region(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(_OFFSET, cancelling)
    assert plan_profile(task(ctx), ctx).diagnostics == (CANCELLED,)


@pytest.mark.req("REQ-PRF-021")
def test_cancelled_after_the_offset_gives_cancelled_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_context()

    def then_cancel(*args: object) -> Result[PolygonRegion]:
        result = offset_region(*args)  # type: ignore[arg-type]
        ctx.cancel.cancel()
        return result

    monkeypatch.setattr(_OFFSET, then_cancel)
    result = plan_profile(task(ctx), ctx)
    assert result.value is None
    assert result.diagnostics == (CANCELLED,)


def _no_offset(*args: object) -> Result[PolygonRegion]:
    raise AssertionError("the offset ran")


@pytest.mark.req("REQ-PRF-012")
def test_a_clockwise_loop_from_offset2d_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # DEC-PRF-007 (6): reversed, the loop would be milled conventional; offset2d broke its promise.
    def clockwise(*args: object) -> Result[PolygonRegion]:
        region = offset_region(*args).value  # type: ignore[arg-type]
        assert region is not None
        back = slice(None, None, -1)
        points, ids = region.points[back].copy(), region.source_ids[back].copy()
        return Result(PolygonRegion(points, region.loop_starts, ids, region.fixed[back].copy()))

    monkeypatch.setattr(_OFFSET, clockwise)
    ctx = make_context()
    with pytest.raises(ValueError, match="not CCW"):
        plan_profile(task(ctx), ctx)


@pytest.mark.req("REQ-PRF-021")
def test_cancelled_at_entry_gives_cancelled_alone_without_the_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = make_context()
    ctx.cancel.cancel()
    monkeypatch.setattr(_OFFSET, _no_offset)
    result = plan_profile(task(ctx), ctx)
    assert result.value is None
    assert result.diagnostics == (CANCELLED,)


@pytest.mark.req("REQ-PRF-020")
def test_every_value_error_is_reported_in_order_and_no_offset_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = make_context()
    monkeypatch.setattr(_OFFSET, _no_offset)
    result = plan_profile(task(ctx, allowance_mm=-6.0, z_bottom_mm=1.0), ctx)
    assert result.value is None
    assert codes(result) == ["PROFILE_ALLOWANCE", "PROFILE_DEPTH_INVALID"]


@pytest.mark.req("REQ-PRF-020")
def test_six_failing_value_checks_report_in_requirement_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = make_context()
    monkeypatch.setattr(_OFFSET, _no_offset)
    tool = FlatEndMill(1, 10.0, 0.5)  # flute 0.5: the depth and the step-down exceed it
    stock = StockBox((1.0, -5.0, -5.0), (105.0, 65.0, 0.5))  # top 0.5, part past x min
    result = plan_profile(task(ctx, tool=tool, stock=stock, z_bottom_mm=-6.0, stepdown_mm=1.0,
                               air_gap_ratio=1e-7), ctx)  # fmt: skip
    assert codes(result) == [
        "PROFILE_FIRST_PASS_DEEP", "PROFILE_BELOW_STOCK", "PROFILE_TOO_DEEP",
        "PROFILE_STEP_DOWN", "PROFILE_STOCK_SMALL", "PROFILE_AIR_GAP",
    ]  # fmt: skip
