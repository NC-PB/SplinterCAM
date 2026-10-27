# SPDX-License-Identifier: Apache-2.0
"""The invariants of src/splintercam/ncx/SPEC.md over generated records, values and fake `ncx`
runs (REQ-NCX-001 to 009, 019 to 024)."""

from dataclasses import replace
from fractions import Fraction

import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from cl_strategies import HEADER, Move, columns, operations
from ncx_fake import MakeFake, Step
from ncx_programs import RECT_FILLETS, exact_text, printed, words
from splintercam.cl import ClOperation, make_cl_data
from splintercam.foundation import Context
from splintercam.ncx import NcxProgram, NcxSection, NcxStep, run_ncx, write_ncx

# The ctx fixture is a frozen value, the same for every example.
_SETTINGS = settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
_MOTION = ("RAPID", "LINE", "ARC=")
_offset = st.integers(0, 2**17).map(lambda k: k * 2.0**-10)


@pytest.mark.req("REQ-NCX-001", "REQ-NCX-002", "REQ-NCX-004", "REQ-NCX-007")
@_SETTINGS
@given(st.lists(operations(), min_size=1, max_size=3), _offset)
def test_the_program_invariants(ctx: Context, passes: list[list[Move]], offset: float) -> None:
    header = replace(HEADER, axial_offset_mm=offset)
    given_ops = tuple(
        ClOperation(replace(header, name=f"OP_{i}"), columns(moves))
        for i, moves in enumerate(passes)
    )
    result = write_ncx(make_cl_data(1, given_ops, ctx), RECT_FILLETS, ctx)
    assert result.value is not None, result.diagnostics
    lines = result.value.text.split("\n")
    assert lines[0] == "FILE=BEGIN NCX=1"
    assert lines[-2:] == ["FILE=END", ""]
    assert result.value.text.isascii()
    assert [line for line in lines if line.startswith("SECTION=")] == [
        f'SECTION="OP_{i}"' for i in range(len(passes))
    ]
    motion = [i for i, line in enumerate(lines) if line.startswith(_MOTION)]
    tools = [i for i, line in enumerate(lines) if line.startswith("TOOL=")]
    units = next(i for i, line in enumerate(lines) if "UNITS=MM" in line)
    assert len(tools) == 1
    assert units < tools[0] < motion[0]
    assert all("F=" not in lines[i] for i in motion if lines[i].startswith("RAPID"))
    # REQ-NCX-007: each written Z within one step of z + a, in move order.
    expected_z = [move.end[2] + offset for moves in passes for move in moves]
    written_z = [float(words(lines[i])["Z"]) for i in motion]
    np.testing.assert_allclose(written_z, expected_z, rtol=0.0, atol=1e-6)


_any = st.floats(-1e9, 1e9, exclude_min=True, exclude_max=True)


@st.composite
def _near_ties(draw: st.DrawFn) -> float:
    # (n + 1/2)·10^-6 and the doubles next to it: the cases a double rounding gets wrong.
    tie = (draw(st.integers(-(10**15) + 1, 10**15 - 2)) + 0.5) / 1e6
    return float(np.nextafter(tie, draw(st.sampled_from((-np.inf, 0.0, np.inf)))))


@pytest.mark.req("REQ-NCX-008", "REQ-NCX-009")
@given(st.lists(st.one_of(_any, _near_ties()), min_size=1, max_size=50))
def test_the_printer_is_exact(values: list[float]) -> None:
    texts = printed(values)
    assert texts == [exact_text(value) for value in values]
    for value, text in zip(values, texts, strict=True):
        assert abs(Fraction(text) - Fraction(value)) <= Fraction(1, 2 * 10**6)


_LINES = {
    "error": "{ncx}(6): ERROR VM440: x\n",
    "warning": "{ncx}(6): WARNING VM300: x\n",
    "rounded": "{ncx}(6): WARNING CMP020: x\n",
    "info": "{ncx}(6): INFO VM001: x\n",
    "garbage": "Unhandled exception\n",
}
_step = st.tuples(st.sampled_from((0, 0, 1, 2)), st.lists(st.sampled_from(sorted(_LINES))))


@pytest.mark.req("REQ-NCX-019", "REQ-NCX-022", "REQ-NCX-023")
@settings(
    max_examples=12, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(st.tuples(_step, _step, _step))
def test_ok_only_when_every_step_passed(
    ctx: Context, fake_ncx: MakeFake, told: tuple[tuple[int, list[str]], ...]
) -> None:
    steps = {
        step.value: Step(exit=code, stderr="".join(_LINES[kind] for kind in kinds))
        for step, (code, kinds) in zip(NcxStep, told, strict=True)
    }
    fake = fake_ncx(**steps)
    program = NcxProgram("", (NcxSection("operation 1 (A)", 5, 50, 0.001),))
    result = run_ncx(fake.call, program, ctx)

    def passed(index: int) -> bool:
        code, kinds = told[index]
        strict = index == 2 and "warning" in kinds
        return code == 0 and "error" not in kinds and not strict

    assert result.ok == all(passed(index) for index in range(3))
    stopped = told[0][0] > 1 or (told[1][0] > 1 and told[0][0] <= 1)
    if not stopped and not (passed(0) and passed(1)):
        assert NcxStep.COMPILE not in fake.ran()
