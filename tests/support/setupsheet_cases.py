# SPDX-License-Identifier: Apache-2.0
"""The setup sheet's example parts (src/splintercam/setupsheet/SPEC.md, Example parts): the golden
job `testdata/zoo/profile-rectangle-fillets/` built by hand as job, record, contour and files."""

import math
from collections.abc import Sequence
from dataclasses import replace

import numpy as np

from cl_strategies import CUT, H_C, H_R, NAN, PLUNGE, Move, arc, columns, line, rapid
from splintercam.cl import ClData, ClHeader, ClOperation, Role, make_cl_data, make_operation
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows, curve_rows
from splintercam.model import FlatEndMill, JobData, Operation, Setup, StockBox
from splintercam.setupsheet import SheetFiles

P = (50.0, -11.0)  # the approach point: S - (R + 0.2·R) in Y (research 10, Method 2; D-079)
S = (50.0, -5.0)  # the pass start on the centre path's bottom edge
PASSES = (-10.0 / 3.0, -20.0 / 3.0, -10.0)
STOCK = StockBox((-5.0, -5.0, -20.0), (105.0, 65.0, 0.0))
TOOL = FlatEndMill(1, 10.0, 30.0)
NAME = "PROFILE_1"
_QUARTER_CW = -math.pi / 2

HEADER = ClHeader(
    name=NAME,
    note=(),
    tool_number=1,
    point_number=1,
    axial_offset_mm=0.0,
    spindle_rpm=8000.0,
    tol_mm=0.01,
    feed_classes=(("plunge", 300.0), ("cut", 1200.0)),
    clearance_height_mm=H_C,
    retract_height_mm=H_R,
)

FILES = SheetFiles(
    program_name="RECT_FILLETS",
    program_number=1,
    ncx_file="RECT_FILLETS.ncx",
    nc_files=("RECT_FILLETS.h",),
    machine_file="heidenhain-itnc530.toml",
    job_file="job.toml",
    part_file="part.dxf",
)


def job_operation(name: str = NAME, tool: int = 1, point: int = 1) -> Operation:
    return Operation(name, "profile", tool, 8000.0, 0.01, (("z_bottom_mm", -10.0),), point)


def golden_job(
    operations: tuple[Operation, ...] | None = None,
    tools: tuple[FlatEndMill, ...] = (TOOL,),
    stock: StockBox = STOCK,
) -> JobData:
    return JobData(tools, Setup(1, stock, operations or (job_operation(),)))


def _loop(z: float) -> list[Move]:
    """The centre path, the part grown by R = 5 (corners R 10), climb, so CW from S."""
    return [
        line(5.0, -5.0, z),
        arc((-5.0, 5.0, z), (5.0, 5.0), _QUARTER_CW),
        line(-5.0, 55.0, z),
        arc((5.0, 65.0, z), (5.0, 55.0), _QUARTER_CW),
        line(95.0, 65.0, z),
        arc((105.0, 55.0, z), (95.0, 55.0), _QUARTER_CW),
        line(105.0, 5.0, z),
        arc((95.0, -5.0, z), (95.0, 5.0), _QUARTER_CW),
        line(*S, z),
    ]


def profile_moves(
    p: tuple[float, float] = P,
    per_pass: Sequence[tuple[float, float]] | None = None,
    plunge_feeds: Sequence[int] = (PLUNGE, PLUNGE, PLUNGE),
) -> list[Move]:
    """The golden record: per pass RAPID to h_r at P, plunge, P → S, the loop, S → P, RAPID h_c.
    With P = S there is no approach line (strategies/profile REQ-PRF-017, d = 0). `per_pass`:
    another P for each pass, reached by a RAPID across at h_c."""
    points = per_pass or (p, p, p)
    moves = [rapid(NAN, NAN, H_C, H_C)]
    for z, at, feed in zip(PASSES, points, plunge_feeds, strict=True):
        if len(moves) == 1 or moves[-1].end[:2] != at:
            moves.append(rapid(*at, H_C, H_C))
        moves += [rapid(*at, H_R, H_R), line(*at, z, Role.APPROACH, feed)]
        if at != S:
            moves.append(line(*S, z, Role.APPROACH, PLUNGE))
        moves += _loop(z)
        if at != S:
            moves.append(line(*at, z, Role.RETRACT, CUT))
        moves.append(rapid(*at, H_C, H_C))
    return moves


def record(
    ctx: Context,
    operations: Sequence[tuple[ClHeader, Sequence[Move]]] | None = None,
    work_offset: int = 1,
) -> ClData:
    """A checked record; by default the golden operation."""
    given = operations or ((HEADER, profile_moves()),)
    built = tuple(make_operation(header, columns(moves), ctx) for header, moves in given)
    return make_cl_data(work_offset, built, ctx)


def renamed(data: ClData, index: int, **header: object) -> ClData:
    """`data` with operation `index`'s header fields replaced, unchecked (as `job` could pass)."""
    operations = list(data.operations)
    old = operations[index]
    operations[index] = ClOperation(replace(old.header, **header), old.moves)
    return ClData(data.work_offset, tuple(operations))


def part(ctx: Context) -> CurveRows:
    """The part, 0 to 100 by 0 to 60 with fillets R 5, CCW."""
    nan, quarter = math.nan, math.pi / 2
    rows = [
        (5.0, 0.0, 95.0, 0.0, nan, nan, 0.0),
        (95.0, 0.0, 100.0, 5.0, 95.0, 5.0, quarter),
        (100.0, 5.0, 100.0, 55.0, nan, nan, 0.0),
        (100.0, 55.0, 95.0, 60.0, 95.0, 55.0, quarter),
        (95.0, 60.0, 5.0, 60.0, nan, nan, 0.0),
        (5.0, 60.0, 0.0, 55.0, 5.0, 55.0, quarter),
        (0.0, 55.0, 0.0, 5.0, nan, nan, 0.0),
        (0.0, 5.0, 5.0, 0.0, 5.0, 5.0, quarter),
    ]
    built = curve_rows(np.array(rows), np.arange(8, dtype=np.int64), np.array([0]), ctx)
    assert built.value is not None, built.diagnostics
    return built.value
