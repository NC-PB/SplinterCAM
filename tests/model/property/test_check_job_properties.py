# SPDX-License-Identifier: Apache-2.0
"""Property tests for `check_job` (model SPEC, Invariants; REQ-MDL-024 to 026, 029): generated
valid jobs, and the same jobs with one field broken at a time."""

import math
from collections.abc import Callable
from dataclasses import replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from model_jobs import DECLARATIONS, PARAMETERS, make_context
from splintercam.foundation import Result, Severity
from splintercam.model import (
    FlatEndMill,
    JobData,
    MeasurementPoint,
    Operation,
    Setup,
    StockBox,
    check_job,
)

_SIZE = st.floats(1.0, 50.0)


@st.composite
def _tool(draw: st.DrawFn, number: int) -> FlatEndMill:
    diameter, flute = draw(_SIZE), draw(_SIZE)
    above = st.floats(0.0, flute)
    points = tuple(MeasurementPoint(k, draw(above), draw(st.floats(0.0, diameter / 2.0)))
                   for k in range(1, draw(st.integers(1, 3)) + 1))  # fmt: skip
    return FlatEndMill(number, diameter, flute, points)


@st.composite
def _jobs(draw: st.DrawFn) -> JobData:
    tools = tuple(draw(_tool(n)) for n in range(1, draw(st.integers(1, 3)) + 1))
    low = draw(st.tuples(_SIZE, _SIZE, _SIZE))
    stock = StockBox(low, (low[0] + draw(_SIZE), low[1] + draw(_SIZE), low[2] + draw(_SIZE)))
    operations: list[Operation] = []
    for index in range(1, draw(st.integers(1, 3)) + 1):
        tool = draw(st.sampled_from(tools))
        given_names = draw(st.permutations(PARAMETERS))
        operations.append(Operation(f"OP_{index}", "profile", tool.number, draw(_SIZE) * 100.0,
                                    draw(st.floats(0.01, 1.0)), tuple(given_names),
                                    draw(st.integers(1, len(tool.points)))))  # fmt: skip
    return JobData(tools, Setup(draw(st.integers(1, 99)), stock, tuple(operations)))


def _errors(result: Result[JobData]) -> list[tuple[str, str | None]]:
    return [(d.code, d.location) for d in result.diagnostics if d.severity is Severity.ERROR]


@pytest.mark.req("REQ-MDL-024")
@given(_jobs())
def test_a_valid_job_comes_back_completed_and_checking_it_again_changes_nothing(
    job: JobData,
) -> None:
    result = check_job(job, DECLARATIONS, make_context())
    assert result.ok
    assert result.value is not None
    # model SPEC, Invariants: a returned job is consistent.
    tools = {tool.number: tool for tool in result.value.tools}
    assert len(tools) == len(result.value.tools)
    assert all(number >= 1 for number in tools)
    declared = DECLARATIONS["profile"]
    for op in result.value.setup.operations:
        assert op.point_number in {p.number for p in tools[op.tool_number].points}
        assert [name for name, _ in op.parameters] == [d.name for d in declared]
        for (_, value), declaration in zip(op.parameters, declared, strict=True):
            low, high = declaration.low, declaration.high
            assert low <= value <= high
            assert not (declaration.low_open and value == low)
    again = check_job(result.value, DECLARATIONS, make_context())
    assert again.value == result.value
    assert hash(again.value) == hash(result.value)


def _first_op(job: JobData, **changes: object) -> JobData:
    ops = (replace(job.setup.operations[0], **changes), *job.setup.operations[1:])
    return replace(job, setup=replace(job.setup, operations=ops))


def _first_tool(job: JobData, **changes: object) -> JobData:
    return replace(job, tools=(replace(job.tools[0], **changes), *job.tools[1:]))


# Each breaker breaks one field of a valid job and names the code and location it must give.
_BREAKERS: list[tuple[Callable[[JobData], JobData], str, Callable[[JobData], str]]] = [
    (lambda j: _first_tool(j, number=True), "VALUE_TYPE_INVALID", lambda j: "tool 1 (TTrue)"),
    (lambda j: _first_tool(j, diameter_mm=-1.0), "TOOL_DIMENSION_INVALID",
     lambda j: "tool 1 (T1)"),
    (lambda j: _first_tool(j, flute_length_mm=math.nan), "TOOL_DIMENSION_INVALID",
     lambda j: "tool 1 (T1)"),
    (lambda j: replace(j, setup=replace(j.setup, work_offset=0)), "SETUP_WORK_OFFSET_INVALID",
     lambda j: "setup"),
    (lambda j: _first_op(j, name="OP 1"), "OP_NAME_INVALID", lambda j: "operation 1 (OP 1)"),
    (lambda j: _first_op(j, spindle_rpm=0.0), "OP_SPINDLE_INVALID",
     lambda j: "operation 1 (OP_1)"),
    (lambda j: _first_op(j, tol_mm=False), "VALUE_TYPE_INVALID", lambda j: "operation 1 (OP_1)"),
    (lambda j: _first_op(j, tool_number=99), "OP_TOOL_UNKNOWN", lambda j: "operation 1 (OP_1)"),
    (lambda j: _first_op(j, parameters=(*PARAMETERS[:3], ("step_down_mm", -1.0),
                                         *PARAMETERS[4:])),
     "PARAM_OUT_OF_RANGE", lambda j: "operation 1 (OP_1), parameter step_down_mm"),
    (lambda j: _first_op(j, parameters=PARAMETERS[:5]), "PARAM_MISSING",
     lambda j: "operation 1 (OP_1), parameter plunge_feed_mm_per_min"),
    (lambda j: replace(j, tools=(*j.tools, j.tools[0])), "TOOL_NUMBER_DUPLICATE",
     lambda j: f"tool {len(j.tools) + 1} (T1)"),
    (lambda j: _first_tool(j, points=(replace(j.tools[0].points[0], register_radius_mm=-1.0),
                                      *j.tools[0].points[1:])),
     "TOOL_POINT_INVALID", lambda j: "tool 1 (T1), point 1"),
    (lambda j: replace(j, setup=replace(j.setup, stock=StockBox(
        j.setup.stock.min_mm, (*j.setup.stock.max_mm[:2], j.setup.stock.min_mm[2])))),
     "STOCK_BOX_INVALID", lambda j: "stock"),
    (lambda j: replace(j, setup=replace(j.setup, operations=(*j.setup.operations,
                                                             j.setup.operations[0]))),
     "OP_NAME_DUPLICATE", lambda j: f"operation {len(j.setup.operations) + 1} (OP_1)"),
    (lambda j: _first_op(j, point_number=9), "OP_POINT_UNKNOWN", lambda j: "operation 1 (OP_1)"),
    (lambda j: _first_op(j, strategy="pocket"), "OP_STRATEGY_UNKNOWN",
     lambda j: "operation 1 (OP_1)"),
    (lambda j: _first_op(j, parameters=(*PARAMETERS, ("zz", 1.0))), "PARAM_UNKNOWN",
     lambda j: "operation 1 (OP_1), parameter zz"),
]  # fmt: skip


@pytest.mark.req("REQ-MDL-022", "REQ-MDL-025", "REQ-MDL-026", "REQ-MDL-029")
@given(_jobs(), st.sampled_from(_BREAKERS))
def test_a_broken_field_gives_its_code_once_at_its_location_and_no_value(
    job: JobData, breaker: tuple[Callable[[JobData], JobData], str, Callable[[JobData], str]]
) -> None:
    break_job, code, location = breaker
    broken = break_job(job)
    result = check_job(broken, DECLARATIONS, make_context())
    assert result.value is None
    assert _errors(result).count((code, location(job))) == 1
    assert [c for c, _ in _errors(result)].count(code) == 1


_GROUPS = ("tool", "stock", "setup", "operation")


@pytest.mark.req("REQ-MDL-026")
@given(_jobs(), st.lists(st.sampled_from(_BREAKERS), min_size=2, max_size=4))
def test_diagnostics_come_in_the_fixed_order(
    job: JobData,
    breakers: list[tuple[Callable[[JobData], JobData], str, Callable[[JobData], str]]],
) -> None:
    for break_job, _, _ in breakers:
        job = break_job(job)
    first = check_job(job, DECLARATIONS, make_context())
    groups = [_GROUPS.index((d.location or "").split(" ")[0]) for d in first.diagnostics]
    assert groups == sorted(groups)
    assert check_job(job, DECLARATIONS, make_context()) == first
