# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the preconditions: the job and the record describe one program (REQ-SHT-001),
and the file names (REQ-SHT-002)."""

from dataclasses import replace

import pytest

from setupsheet_cases import (
    FILES,
    HEADER,
    TOOL,
    golden_job,
    job_operation,
    part,
    profile_moves,
    record,
    renamed,
)
from splintercam.foundation import Context
from splintercam.model import MeasurementPoint
from splintercam.setupsheet import make_setup_sheet


@pytest.mark.req("REQ-SHT-001")
def test_the_golden_job_and_record_agree(ctx: Context) -> None:
    sheet = make_setup_sheet(golden_job(), record(ctx), part(ctx), FILES, ctx)
    assert sheet.work_offset == 1


@pytest.mark.req("REQ-SHT-001")
def test_another_work_offset_is_refused(ctx: Context) -> None:
    with pytest.raises(ValueError, match=r"work_offset: 2 in the record, 1 in the job"):
        make_setup_sheet(golden_job(), record(ctx, work_offset=2), part(ctx), FILES, ctx)


@pytest.mark.req("REQ-SHT-001")
def test_other_operations_or_another_order_are_refused(ctx: Context) -> None:
    two = (job_operation("A"), job_operation("B"))
    swapped = record(ctx, ((replace(HEADER, name="B"), profile_moves()),
                           (replace(HEADER, name="A"), profile_moves())))  # fmt: skip
    with pytest.raises(ValueError, match=r"operation 'B': name: the job's operation 0 is 'A'"):
        make_setup_sheet(golden_job(two), swapped, part(ctx), FILES, ctx)
    one = record(ctx, ((replace(HEADER, name="A"), profile_moves()),))
    with pytest.raises(ValueError, match=r"operations: 1 in the record, 2 in the job"):
        make_setup_sheet(golden_job(two), one, part(ctx), FILES, ctx)


@pytest.mark.req("REQ-SHT-001")
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("tool_number", 2, r"tool_number: 2 in the record, 1 in the job"),
        ("point_number", 2, r"point_number: 2 in the record, 1 in the job"),
        ("axial_offset_mm", 3.0, r"axial_offset_mm: 3.0 in the record, 0.0 in the job"),
        ("spindle_rpm", 8001.0, r"spindle_rpm: 8001.0 in the record, 8000.0 in the job"),
    ],
)
def test_a_header_field_off_the_job_is_refused(
    ctx: Context, field: str, value: object, message: str
) -> None:
    # Point 2 exists on the tool, so the point number is refused for the mismatch, not a lookup.
    tool = replace(TOOL, points=(*TOOL.points, MeasurementPoint(2, 0.0, 0.0)))
    job = golden_job(tools=(tool,))
    data = renamed(record(ctx), 0, **{field: value})
    with pytest.raises(ValueError, match=r"^setup sheet: operation 'PROFILE_1': " + message):
        make_setup_sheet(job, data, part(ctx), FILES, ctx)


@pytest.mark.req("REQ-SHT-001")
def test_a_one_ulp_axial_offset_is_refused(ctx: Context) -> None:
    data = renamed(record(ctx), 0, axial_offset_mm=5e-324)
    with pytest.raises(ValueError, match=r"axial_offset_mm"):
        make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx)


@pytest.mark.req("REQ-SHT-001")
def test_a_minus_zero_axial_offset_is_accepted(ctx: Context) -> None:
    data = renamed(record(ctx), 0, axial_offset_mm=-0.0)
    sheet = make_setup_sheet(golden_job(), data, part(ctx), FILES, ctx)
    assert sheet.operations[0].axial_offset_mm == 0.0


@pytest.mark.req("REQ-SHT-002")
@pytest.mark.parametrize(
    "field", ["program_name", "ncx_file", "machine_file", "job_file", "part_file"]
)
@pytest.mark.parametrize("bad", ["", "out/x", "C:\\out\\x"])
def test_a_file_name_empty_or_with_a_folder_is_refused(ctx: Context, field: str, bad: str) -> None:
    files = replace(FILES, **{field: bad})
    with pytest.raises(ValueError, match=rf"^setup sheet: files\.{field}: "):
        make_setup_sheet(golden_job(), record(ctx), part(ctx), files, ctx)


@pytest.mark.req("REQ-SHT-002")
def test_the_compiled_files_are_checked(ctx: Context) -> None:
    for nc_files, where in (((), r"no compiled file"), (("A.h", "b/B.h"), r"\[1\]")):
        files = replace(FILES, nc_files=nc_files)
        with pytest.raises(ValueError, match=rf"^setup sheet: files\.nc_files.*{where}"):
            make_setup_sheet(golden_job(), record(ctx), part(ctx), files, ctx)


@pytest.mark.req("REQ-SHT-002")
def test_the_program_number_is_at_least_1(ctx: Context) -> None:
    with pytest.raises(ValueError, match=r"^setup sheet: files\.program_number: 0"):
        make_setup_sheet(golden_job(), record(ctx), part(ctx), replace(FILES, program_number=0),
                         ctx)  # fmt: skip


@pytest.mark.req("REQ-SHT-002")
def test_the_files_are_held_as_given(ctx: Context) -> None:
    sheet = make_setup_sheet(golden_job(), record(ctx), part(ctx), FILES, ctx)
    assert sheet.files == FILES
