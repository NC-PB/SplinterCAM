# SPDX-License-Identifier: Apache-2.0
"""Unit tests for model's job data and `check_job` (model SPEC, REQ-MDL-001 to 029; the SPEC's
example parts)."""

import dataclasses
import math
from dataclasses import replace

import pytest

from model_jobs import (
    DECLARATIONS,
    PARAMETERS,
    PROFILE,
    declaration,
    example_job,
    make_context,
    operation,
)
from splintercam.foundation import Context, Result, Severity
from splintercam.model import (
    TIP,
    FlatEndMill,
    JobData,
    MeasurementPoint,
    ParameterDeclaration,
    Setup,
    StockBox,
    Unit,
    check_job,
)


def _check(job: JobData) -> Result[JobData]:
    return check_job(job, DECLARATIONS, make_context())


def _codes(result: Result[JobData]) -> list[str]:
    return [d.code for d in result.diagnostics]


def _with_tool(tool: FlatEndMill) -> JobData:
    return replace(example_job(), tools=(tool,))


def _with_setup(**changes: object) -> JobData:
    job = example_job()
    return replace(job, setup=replace(job.setup, **changes))


def _with_op(**changes: object) -> JobData:
    return example_job((replace(operation(), **changes),))


def _with_params(*parameters: tuple[object, ...]) -> JobData:
    return _with_op(parameters=parameters)


def _only(result: Result[JobData], code: str) -> str:
    assert not result.ok
    assert result.value is None
    assert _codes(result) == [code]
    location = result.diagnostics[0].location
    assert location is not None
    return location


# --- the example job and the types (REQ-MDL-001, 007, 009, 011, 024) ---------------------------


@pytest.mark.req("REQ-MDL-001", "REQ-MDL-007", "REQ-MDL-009", "REQ-MDL-011", "REQ-MDL-024")
def test_the_example_job_passes_with_every_parameter_completed() -> None:
    result = _check(example_job())
    assert result.ok
    assert result.diagnostics == ()
    assert result.value is not None
    op = result.value.setup.operations[0]
    assert op.parameters == (*PARAMETERS, ("air_gap_ratio", 0.2))
    assert replace(op, parameters=PARAMETERS) == operation()
    assert replace(result.value, setup=example_job().setup) == example_job()


@pytest.mark.req("REQ-MDL-001")
def test_a_flat_end_mill_defaults_to_the_tip() -> None:
    tool = FlatEndMill(1, 10.0, 30.0)
    assert tool.points == (TIP,)
    assert MeasurementPoint(1, 0.0, 0.0) == TIP
    assert tool.radius_mm == 5.0


@pytest.mark.req("REQ-MDL-007")
def test_the_stock_top_is_the_largest_z() -> None:
    assert StockBox((-5.0, -5.0, -20.0), (105.0, 65.0, 0.0)).top_mm == 0.0


@pytest.mark.req("REQ-MDL-011")
def test_an_operation_uses_point_1_by_default() -> None:
    assert operation().point_number == 1


@pytest.mark.req("REQ-MDL-024")
def test_values_are_completed_in_declaration_order_whatever_the_input_order() -> None:
    result = _check(_with_params(*reversed(PARAMETERS), ("air_gap_ratio", 1)))
    assert result.value is not None
    assert [name for name, _ in result.value.setup.operations[0].parameters] == [
        d.name for d in PROFILE
    ]
    assert result.value.setup.operations[0].parameters[-1] == ("air_gap_ratio", 1.0)


@pytest.mark.req("REQ-MDL-024")
def test_values_are_immutable_and_a_checked_job_is_hashable() -> None:
    # model SPEC, Invariants: immutable values, held in memory.
    result = _check(example_job())
    assert result.value is not None
    hash(result.value)
    for value in (TIP, FlatEndMill(1, 10.0, 30.0), result.value, PROFILE[0]):
        field = dataclasses.fields(value)[0].name
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(value, field, 2)


# --- tools (REQ-MDL-002 to 006) -------------------------------------------------------------------


@pytest.mark.req("REQ-MDL-002", "REQ-MDL-027")
def test_tool_number_below_1() -> None:
    result = _check(_with_tool(FlatEndMill(0, 10.0, 30.0)))
    # The operation still names T1, which this job no longer has.
    assert [(d.code, d.location) for d in result.diagnostics] == [
        ("TOOL_NUMBER_INVALID", "tool 1 (T0)"),
        ("OP_TOOL_UNKNOWN", "operation 1 (PROFILE_1)"),
    ]
    assert result.value is None


@pytest.mark.req("REQ-MDL-003")
@pytest.mark.parametrize("value", [0.0, -1.0, math.nan, math.inf])
def test_tool_dimension_not_finite_or_not_above_0(value: float) -> None:
    for field in ("diameter_mm", "flute_length_mm"):
        result = _check(_with_tool(replace(FlatEndMill(1, 10.0, 30.0), **{field: value})))
        _only(result, "TOOL_DIMENSION_INVALID")
        assert repr(value) in result.diagnostics[0].message
        assert field in result.diagnostics[0].message


@pytest.mark.req("REQ-MDL-004", "REQ-MDL-026")
def test_a_repeated_tool_number_is_reported_on_the_second() -> None:
    job = replace(example_job(), tools=(FlatEndMill(1, 10.0, 30.0), FlatEndMill(1, 6.0, 20.0)))
    assert _only(_check(job), "TOOL_NUMBER_DUPLICATE") == "tool 2 (T1)"


@pytest.mark.req("REQ-MDL-005")
@pytest.mark.parametrize("numbers", [(), (2,), (1, 3), (2, 1), (1, 1)])
def test_points_numbered_other_than_1_to_n(numbers: tuple[int, ...]) -> None:
    points = tuple(MeasurementPoint(k, 0.0, 0.0) for k in numbers)
    expected = ["TOOL_POINT_NUMBERS"] + (["OP_POINT_UNKNOWN"] if 1 not in numbers else [])
    assert _codes(_check(_with_tool(FlatEndMill(1, 10.0, 30.0, points)))) == expected


@pytest.mark.req("REQ-MDL-006", "REQ-MDL-027")
@pytest.mark.parametrize(
    ("a", "r"),
    [(-0.1, 0.0), (math.nan, 0.0), (math.inf, 0.0), (0.0, -0.1), (0.0, 5.1), (0.0, math.nan),
     (0.0, math.inf)],
)  # fmt: skip
def test_point_outside_its_range(a: float, r: float) -> None:
    point = MeasurementPoint(2, a, r)
    location = _only(_check(_with_tool(FlatEndMill(1, 10.0, 30.0, (TIP, point)))),
                     "TOOL_POINT_INVALID")  # fmt: skip
    assert location == "tool 1 (T1), point 2"


@pytest.mark.req("REQ-MDL-006")
def test_point_on_the_edge_of_its_range_passes() -> None:
    points = (TIP, MeasurementPoint(2, 30.0, 5.0))
    assert _check(_with_tool(FlatEndMill(1, 10.0, 30.0, points))).diagnostics == ()


@pytest.mark.req("REQ-MDL-006")
def test_point_above_the_flute_is_kept_with_a_warning_naming_the_shift() -> None:
    points = (MeasurementPoint(1, 40.0, 5.0),)
    result = _check(_with_tool(FlatEndMill(1, 10.0, 30.0, points)))
    assert result.ok
    assert _codes(result) == ["TOOL_POINT_ABOVE_FLUTE"]
    assert result.diagnostics[0].severity is Severity.WARNING
    assert "every Z is output 40 mm above the tip" in result.diagnostics[0].message
    assert result.value is not None
    assert result.value.tools[0].points == points


@pytest.mark.req("REQ-MDL-006")
def test_point_checks_are_skipped_for_an_invalid_dimension() -> None:
    points = (MeasurementPoint(1, -1.0, 9.0),)
    for tool in (FlatEndMill(1, -10.0, 30.0, points), FlatEndMill(1, 10.0, math.nan, points)):
        assert _codes(_check(_with_tool(tool))) == ["TOOL_DIMENSION_INVALID"]


@pytest.mark.req("REQ-MDL-006", "REQ-MDL-027")
def test_a_point_is_located_by_its_number() -> None:
    result = _check(_with_tool(FlatEndMill(1, 10.0, 30.0, (TIP, MeasurementPoint(3, -1.0, 0.0)))))
    assert [(d.code, d.location) for d in result.diagnostics] == [
        ("TOOL_POINT_NUMBERS", "tool 1 (T1)"),
        ("TOOL_POINT_INVALID", "tool 1 (T1), point 3"),
    ]


# --- stock and setup (REQ-MDL-008 to 010) ---------------------------------------------------------


@pytest.mark.req("REQ-MDL-008")
@pytest.mark.parametrize(("axis", "top"), [(0, 1e-12), (1, -1.0), (2, math.nan), (2, math.inf)])
def test_stock_extent_not_above_eps_or_not_finite(axis: int, top: float) -> None:
    corner = [10.0, 10.0, 10.0]
    corner[axis] = top
    result = _check(_with_setup(stock=StockBox((0.0, 0.0, 0.0), (corner[0], corner[1], corner[2]))))
    assert _only(result, "STOCK_BOX_INVALID") == "stock"
    assert f"{'xyz'[axis]} " in result.diagnostics[0].message


@pytest.mark.req("REQ-MDL-008")
def test_stock_extent_equal_to_eps_or_a_non_finite_low_corner() -> None:
    eps = make_context().tolerances.length_eps_mm
    for low, high in (((0.0, 0.0, -math.inf), (10.0, 10.0, 10.0)),
                      ((0.0, 0.0, 0.0), (10.0, 10.0, eps))):  # fmt: skip
        result = _check(_with_setup(stock=StockBox(low, high)))
        assert _only(result, "STOCK_BOX_INVALID") == "stock"
        assert "z " in result.diagnostics[0].message


@pytest.mark.req("REQ-MDL-009")
def test_a_setup_without_operations() -> None:
    assert _only(_check(_with_setup(operations=())), "SETUP_NO_OPERATION") == "setup"


@pytest.mark.req("REQ-MDL-010")
def test_work_offset_below_1() -> None:
    assert _only(_check(_with_setup(work_offset=0)), "SETUP_WORK_OFFSET_INVALID") == "setup"


# --- operations (REQ-MDL-012 to 016) --------------------------------------------------------------


@pytest.mark.req("REQ-MDL-012", "REQ-MDL-027")
@pytest.mark.parametrize("name", ["", "Profile 1", "PROFIL_Ä", "P-1"])
def test_operation_name_with_other_characters(name: str) -> None:
    assert _only(_check(_with_op(name=name)), "OP_NAME_INVALID") == f"operation 1 ({name})"


@pytest.mark.req("REQ-MDL-013")
def test_a_repeated_operation_name_is_reported_on_the_second() -> None:
    job = example_job((operation(), operation()))
    assert _only(_check(job), "OP_NAME_DUPLICATE") == "operation 2 (PROFILE_1)"


@pytest.mark.req("REQ-MDL-014")
def test_operation_naming_a_missing_tool_or_point() -> None:
    _only(_check(_with_op(tool_number=2)), "OP_TOOL_UNKNOWN")
    _only(_check(_with_op(point_number=2)), "OP_POINT_UNKNOWN")


@pytest.mark.req("REQ-MDL-015")
@pytest.mark.parametrize("rpm", [0.0, -8000.0, math.nan, math.inf])
def test_spindle_speed_not_finite_or_not_above_0(rpm: float) -> None:
    _only(_check(_with_op(spindle_rpm=rpm)), "OP_SPINDLE_INVALID")


@pytest.mark.req("REQ-MDL-016")
@pytest.mark.parametrize(
    ("tol", "code"),
    [(math.nan, "OP_TOL_INVALID"), (math.inf, "OP_TOL_INVALID"),
     (0.001, "TOL_BELOW_MINIMUM"), (2.0, "TOL_ABOVE_MAXIMUM")],
)  # fmt: skip
def test_tolerance_is_checked_by_foundation(tol: float, code: str) -> None:
    assert _only(_check(_with_op(tol_mm=tol)), code) == "operation 1 (PROFILE_1)"


# --- declarations and parameter values (REQ-MDL-017 to 023) ---------------------------------------


@pytest.mark.req("REQ-MDL-017")
def test_a_declaration_holds_its_fields() -> None:
    feed = declaration("cut_feed_mm_per_min", Unit.MM_PER_MIN, None, low_open=True)
    assert (feed.unit.value, feed.default, feed.low, feed.high) == ("mm/min", None, 0.0, math.inf)
    assert (feed.low_open, feed.high_open, Unit.RATIO.value) == (True, True, "1")


@pytest.mark.req("REQ-MDL-018")
@pytest.mark.parametrize(
    ("changes", "problem"),
    [({"name": "step down"}, "identifier"), ({"name": ""}, "identifier"),
     ({"unit": "mm"}, "Unit"), ({"source": ""}, "source"),
     ({"low": math.nan}, "NaN"), ({"high": math.nan}, "NaN"),
     ({"low": math.inf}, "no finite value"), ({"low": 1.0, "high": 0.0}, "no finite value"),
     ({"low": 1.0, "high": 1.0, "low_open": True}, "no finite value"),
     ({"low": -math.inf, "high": -math.inf}, "no finite value"),
     ({"default": math.nan}, "default"), ({"default": -1.0}, "default"),
     ({"low_open": True, "default": 0.0}, "default")],
)  # fmt: skip
def test_an_invalid_declaration_raises(changes: dict[str, object], problem: str) -> None:
    # The default is None unless the case sets it, so only the check under test can raise.
    with pytest.raises(ValueError, match=f"parameter declaration .*{problem}"):
        replace(PROFILE[0], **{"low": 0.0, "default": None, **changes})


@pytest.mark.req("REQ-MDL-018")
def test_a_point_range_with_closed_ends_is_valid() -> None:
    ParameterDeclaration("x", Unit.MM, 1.0, 1.0, 1.0, False, False, "ours")


@pytest.mark.req("REQ-MDL-019")
def test_repeated_declared_names_raise_before_any_check(ctx: Context) -> None:
    ctx.cancel.cancel()
    with pytest.raises(ValueError, match="z_top_mm"):
        check_job(example_job(), {"profile": (*PROFILE, PROFILE[1])}, ctx)


@pytest.mark.req("REQ-MDL-020")
def test_an_unknown_strategy_skips_the_parameter_checks() -> None:
    assert _only(_check(_with_op(strategy="pocket", parameters=(("x", math.nan),))),
                 "OP_STRATEGY_UNKNOWN") == "operation 1 (PROFILE_1)"  # fmt: skip


@pytest.mark.req("REQ-MDL-021", "REQ-MDL-027")
def test_unknown_and_repeated_names() -> None:
    result = _check(_with_params(*PARAMETERS, ("stepdown_mm", 2.0)))
    assert _only(result, "PARAM_UNKNOWN") == "operation 1 (PROFILE_1), parameter stepdown_mm"
    _only(_check(_with_params(*PARAMETERS, ("step_down_mm", 2.0))), "PARAM_REPEATED")


@pytest.mark.req("REQ-MDL-022")
def test_the_example_without_its_feeds() -> None:
    result = _check(_with_params(*PARAMETERS[:4]))
    assert _codes(result) == ["PARAM_MISSING", "PARAM_MISSING"]
    assert result.value is None
    assert "cut_feed_mm_per_min" in result.diagnostics[0].message
    assert "mm/min" in result.diagnostics[0].message


@pytest.mark.req("REQ-MDL-023")
@pytest.mark.parametrize("feed", [0.0, -1.0, math.nan, math.inf])
def test_a_value_outside_its_range_names_value_range_and_unit(feed: float) -> None:
    params = tuple((n, feed if n == "cut_feed_mm_per_min" else v) for n, v in PARAMETERS)
    result = _check(_with_params(*params))
    _only(result, "PARAM_OUT_OF_RANGE")
    assert all(s in result.diagnostics[0].message for s in (repr(feed), "(0, inf)", "mm/min"))


@pytest.mark.req("REQ-MDL-023")
def test_a_closed_end_takes_its_value_and_is_named_with_a_bracket(ctx: Context) -> None:
    ratio = ParameterDeclaration("ratio", Unit.RATIO, None, 0.0, 1.0, False, False, "ours")
    declarations = {"profile": (*PROFILE, ratio)}
    for value, ok in ((0.0, True), (1.0, True), (1.5, False)):
        result = check_job(_with_params(*PARAMETERS, ("ratio", value)), declarations, ctx)
        assert result.ok is ok
        assert ok or "[0, 1]" in result.diagnostics[0].message


# --- order, locations, cancellation, types (REQ-MDL-025 to 029) -----------------------------------


@pytest.mark.req("REQ-MDL-025", "REQ-MDL-026", "REQ-MDL-027")
def test_every_diagnostic_in_the_fixed_order_with_its_location() -> None:
    tools = (FlatEndMill(0, 10.0, 30.0), FlatEndMill(2, True, 30.0))
    params = (("zz", 1.0), ("aa", 1.0), *PARAMETERS[1:])
    bad = replace(operation("A B", params), spindle_rpm=0.0, tool_number=2)
    job = JobData(tools, Setup(0, StockBox((0.0, 0.0, 0.0), (1.0, 1.0, 0.0)), (bad,)))
    result = _check(job)
    assert [(d.code, d.location) for d in result.diagnostics] == [
        ("TOOL_NUMBER_INVALID", "tool 1 (T0)"),
        ("VALUE_TYPE_INVALID", "tool 2 (T2)"),
        ("STOCK_BOX_INVALID", "stock"),
        ("SETUP_WORK_OFFSET_INVALID", "setup"),
        ("OP_NAME_INVALID", "operation 1 (A B)"),
        ("OP_SPINDLE_INVALID", "operation 1 (A B)"),
        ("PARAM_UNKNOWN", "operation 1 (A B), parameter aa"),
        ("PARAM_UNKNOWN", "operation 1 (A B), parameter zz"),
    ]
    assert result.value is None


@pytest.mark.req("REQ-MDL-021", "REQ-MDL-025", "REQ-MDL-026")
def test_the_order_within_a_tool_and_within_an_operation() -> None:
    tools = (FlatEndMill(1, 10.0, 30.0), FlatEndMill(1, -6.0, 20.0, ()))
    params = (*PARAMETERS[:3], ("step_down_mm", -1.0), ("step_down_mm", -2.0), *PARAMETERS[4:],
              ("zz", 1.0), ("zz", 2.0))  # fmt: skip
    op = replace(operation("A B", params), spindle_rpm="fast")
    at = "operation 1 (A B), parameter"
    result = _check(replace(example_job((op,)), tools=tools))
    assert [(d.code, d.location) for d in result.diagnostics] == [
        ("TOOL_DIMENSION_INVALID", "tool 2 (T1)"),
        ("TOOL_NUMBER_DUPLICATE", "tool 2 (T1)"),
        ("TOOL_POINT_NUMBERS", "tool 2 (T1)"),
        ("VALUE_TYPE_INVALID", "operation 1 (A B)"),
        ("OP_NAME_INVALID", "operation 1 (A B)"),
        ("PARAM_REPEATED", f"{at} step_down_mm"),
        ("PARAM_OUT_OF_RANGE", f"{at} step_down_mm"),
        ("PARAM_OUT_OF_RANGE", f"{at} step_down_mm"),
        ("PARAM_UNKNOWN", f"{at} zz"),
        ("PARAM_REPEATED", f"{at} zz"),
    ]


@pytest.mark.req("REQ-MDL-028")
def test_cancelled_at_entry(ctx: Context) -> None:
    ctx.cancel.cancel()
    result = check_job(replace(example_job(), tools=()), DECLARATIONS, ctx)
    assert result.value is None
    assert _codes(result) == ["CANCELLED"]


@pytest.mark.req("REQ-MDL-029")
@pytest.mark.parametrize(
    "job",
    [
        _with_tool(FlatEndMill(True, 10.0, 30.0)),  # JSON true read as T1
        _with_tool(FlatEndMill(1, "10", 30.0)),  # type: ignore[arg-type]
        _with_tool(FlatEndMill(1, 10.0, 30.0, (MeasurementPoint(1, 0.0, None),))),  # type: ignore[arg-type]
        _with_tool(FlatEndMill(1, 10.0, 30.0, [TIP])),  # type: ignore[arg-type]
        replace(example_job(), tools=[FlatEndMill(1, 10.0, 30.0)]),
        _with_setup(stock=StockBox((0.0, 0.0), (1.0, 1.0, 1.0))),  # type: ignore[arg-type]
        _with_setup(work_offset=1.0),
        _with_setup(operations=[operation()]),
        _with_setup(stock=None),
        replace(example_job(), setup=None),
        _with_op(tol_mm=True),
        _with_op(spindle_rpm=10**400),
        _with_op(name=1),
        _with_params(*PARAMETERS, ("air_gap_ratio", "0.2")),
        _with_params(*PARAMETERS, ("air_gap_ratio",)),
    ],
)
def test_a_value_of_the_wrong_type(job: JobData) -> None:
    result = _check(job)
    assert result.value is None
    assert _codes(result)[0] == "VALUE_TYPE_INVALID"
    assert set(_codes(result)) <= {"VALUE_TYPE_INVALID", "OP_TOOL_UNKNOWN", "OP_POINT_UNKNOWN"}


@pytest.mark.req("REQ-MDL-029")
def test_an_int_length_is_accepted_and_the_wrong_type_is_named() -> None:
    assert _check(_with_tool(FlatEndMill(1, 10, 30))).ok
    message = _check(_with_tool(FlatEndMill(1, "10", 30.0))).diagnostics[0].message  # type: ignore[arg-type]
    assert "diameter_mm" in message
    assert "str" in message
