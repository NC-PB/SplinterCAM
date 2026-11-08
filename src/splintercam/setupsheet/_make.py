# SPDX-License-Identifier: Apache-2.0
"""`make_setup_sheet`: the sheet's values for one program of one setup (setupsheet SPEC)."""

from splintercam.cl import ClData
from splintercam.foundation import Context
from splintercam.geometry2d import CurveRows, row_boxes
from splintercam.model import FlatEndMill, JobData, MeasurementPoint

from ._checks import Planned, check_agreement, check_files
from ._operation import sheet_operation
from ._types import Box3, SetupSheet, SheetFiles, SheetOperation, SheetPoint, SheetTool

# Peter's keep-clear margin round the reach, in X and Y (AQ-035 item 2: the band's margin over
# the tool's edge; AQ-056 item 1, provisional; DEC-SHT-002).
KEEP_CLEAR_MARGIN_MM = 5.0


def _tools(planned: tuple[Planned, ...]) -> tuple[SheetTool, ...]:
    # REQ-SHT-008: each tool once, in the order of first use, with the points used, k ascending.
    used: dict[int, tuple[FlatEndMill, dict[int, MeasurementPoint]]] = {}
    for _, tool, point in planned:  # dicts keep insertion order: the order of first use
        used.setdefault(tool.number, (tool, {}))[1][point.number] = point
    tools: list[SheetTool] = []
    for tool, points in used.values():
        listed = [
            SheetPoint(p.number, p.axial_offset_mm, p.register_radius_mm)
            for _, p in sorted(points.items())
        ]
        tools.append(SheetTool(tool.number, tool.diameter_mm, tool.flute_length_mm, tuple(listed)))
    return tuple(tools)


def _keep_out(
    operations: tuple[SheetOperation, ...], stock: Box3
) -> tuple[Box3 | None, Box3 | None, float | None]:
    # REQ-SHT-012: the union of the reaches, the keep-clear box, and holds_below where the reach
    # covers the stock box in XY (research 10, trap 1; DEC-SHT-002).
    boxes = [op.reach for op in operations if op.reach is not None]
    if not boxes:
        return None, None, None
    x0, y0, z0 = (min(b.min_mm[i] for b in boxes) for i in range(3))
    x1, y1, z1 = (max(b.max_mm[i] for b in boxes) for i in range(3))
    reach = Box3((x0, y0, z0), (x1, y1, z1))
    m = KEEP_CLEAR_MARGIN_MM
    keep_clear = Box3((x0 - m, y0 - m, z0), (x1 + m, y1 + m, z1))
    covers = x0 <= stock.min_mm[0] and y0 <= stock.min_mm[1]
    covers = covers and stock.max_mm[0] <= x1 and stock.max_mm[1] <= y1
    return reach, keep_clear, (z0 if covers else None)


def make_setup_sheet(
    job: JobData, cl: ClData, part: CurveRows, files: SheetFiles, ctx: Context
) -> SetupSheet:
    """The setup sheet's values, unrounded. `job` from `model.check_job`, `cl` from
    `cl.make_cl_data` for that job's setup; refuses a mismatch or a broken file name with
    `ValueError` (REQ-SHT-001, 002, 011). Reads no clock, locale or environment (REQ-SHT-019).

    Implements: REQ-SHT-001, 002, 005 to 016 (values), 019.
    """
    check_files(files)
    planned = check_agreement(job, cl)
    setup = job.setup
    stock = Box3(setup.stock.min_mm, setup.stock.max_mm)
    operations = tuple(
        sheet_operation(written, match, setup.stock, ctx)
        for written, match in zip(cl.operations, planned, strict=True)
    )
    boxes = row_boxes(part.rows, ctx)  # REQ-SHT-005: the union of the rows' boxes
    x0, y0 = boxes[:, :2].min(axis=0).tolist()
    x1, y1 = boxes[:, 2:].max(axis=0).tolist()
    reach, keep_clear, holds_below = _keep_out(operations, stock)
    return SetupSheet(
        files=files,
        part_box_xy_mm=(x0, y0, x1, y1),
        work_offset=setup.work_offset,
        stock=stock,
        tools=_tools(planned),
        operations=operations,
        reach=reach,
        keep_clear=keep_clear,
        holds_below_mm=holds_below,
        rapid_floor_mm=min(op.clearance_mm for op in operations),
        reaches_stock_bottom=min(op.lowest_mm for op in operations) <= stock.min_mm[2],
    )
