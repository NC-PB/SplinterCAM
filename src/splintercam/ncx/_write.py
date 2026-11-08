# SPDX-License-Identifier: Apache-2.0
"""`write_ncx`: the record as one program of canonical NCX (REQ-NCX-001 to 017; research 26,
Mapping onto NCX)."""

from dataclasses import replace
from importlib.metadata import version

import numpy as np

from splintercam.cl import ClData, ClOperation, make_cl_data
from splintercam.foundation import Context, Result, ToleranceSet

from ._moves import Printed, move_blocks, printed
from ._printer import to_steps, to_text
from ._refusals import operation_errors, program_errors
from ._types import NcxProgram, NcxSection, ProgramInfo

# Research 26, Mapping onto NCX: a complete header before any motion (VM200).
_MODES = "FEED_MODE=PER_MIN COMP=OFF UNITS=MM WORKPLANE=XY CYCLE=OFF"
# DEC-NCX-008: spindle and coolant off before the program end (AQ-010 item 2; RR-006).
_END = ("COOLANT=OFF", "SPINDLE=OFF", "PROGRAM=END", "FILE=END")
_UNTESTED = "not yet tested on a machine, plan 0007 step 8"


def _round_limit(where: str, tol_mm: float) -> Result[float]:
    # REQ-NCX-009: the reserve share of the operation's tolerance set (D-149, REQ-FND-009).
    built = ToleranceSet.for_operation(tol_mm)
    if built.value is None:  # a tol cl accepts but foundation does not (DEC-NCX-012)
        return Result(None, tuple(replace(d, location=where) for d in built.diagnostics))
    return Result(built.value.stage_tol_mm("reserve"))


def _note() -> str:
    # REQ-NCX-028 (Peter, 2026-11-08); no bracket: NCXchange D390 warns on one (DEC-NCX-021).
    return f'COMMENT="SplinterCAM {version("splintercam")}: {_UNTESTED}"'


def _tool_block(operation: ClOperation) -> str:
    # D-155: the operation's point k, its axial offset a and register radius r, so the machine
    # file maps tool and k to the control's register (NCXchange D372 to D376 at 1e2fd00). They
    # replace OFFSET:LEN (research 26, Checked condition 1). r is 0: cl has no r yet and COMP is
    # OFF (DEC-NCX-020, AQ-050).
    header = operation.header
    rpm, tip = to_text(to_steps(np.array([header.spindle_rpm, header.axial_offset_mm])))
    point = f"TOOL_POINT={header.point_number} TIP_OFFSET={tip} POINT_RADIUS=0.0"
    return f"TOOL={header.tool_number} {point} SPINDLE=CW RPM={rpm}"


def _operation_blocks(index: int, operation: ClOperation, columns: Printed) -> list[str]:
    # REQ-NCX-002: SECTION, the note, the tool block in the first operation only, the moves.
    header = operation.header
    blocks = [f'SECTION="{header.name}"', *(f'COMMENT="{line}"' for line in header.note)]
    if index == 1:
        blocks += [_tool_block(operation), "COOLANT=ON"]
    return blocks + move_blocks(operation, columns)


def write_ncx(cl: ClData, program: ProgramInfo, ctx: Context) -> Result[NcxProgram]:
    """The canonical NCX text of `cl` as program `program`, the same for every machine, with
    each operation's lines; or no program and every error in the order of REQ-NCX-017.

    Rebuilds `cl` with `make_cl_data` first; a broken record raises its `ValueError`. Writes no
    file, starts no process and does not poll `ctx.cancel` (DEC-CL-002).

    Implements: REQ-NCX-001 to 017.
    """
    data = make_cl_data(cl.work_offset, cl.operations, ctx)
    first = data.operations[0].header
    errors = program_errors(program.name, program.number)
    lines = [
        "FILE=BEGIN NCX=1",
        f'PROGRAM=BEGIN NAME="{program.name}" NUMBER={program.number}',
        _MODES,
        f"ORIGIN={data.work_offset}",
        _note(),
    ]
    sections: list[NcxSection] = []
    for index, operation in enumerate(data.operations, start=1):
        where = f"operation {index} ({operation.header.name})"
        columns = printed(operation)
        errors += operation_errors(where, operation, first, columns)
        limit = _round_limit(where, operation.header.tol_mm)
        errors += limit.diagnostics
        if errors or limit.value is None:
            continue
        start = len(lines) + 1
        lines += _operation_blocks(index, operation, columns)
        sections.append(NcxSection(where, start, len(lines), limit.value))
    if errors:
        return Result(None, tuple(errors))
    text = "\n".join((*lines, *_END)) + "\n"
    return Result(NcxProgram(text, tuple(sections)))
