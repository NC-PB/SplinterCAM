# SPDX-License-Identifier: Apache-2.0
"""The preconditions: the record is the job's program (REQ-SHT-001, DEC-SHT-004) and the files
are names only (REQ-SHT-002, DEC-SHT-006). Both are programming errors in `job`: `ValueError`."""

from splintercam.cl import ClData
from splintercam.model import FlatEndMill, JobData, MeasurementPoint, Operation

from ._types import SheetFiles

PREFIX = "setup sheet: "
_NAMED = ("program_name", "ncx_file", "machine_file", "job_file", "part_file")

Planned = tuple[Operation, FlatEndMill, MeasurementPoint]


def check_files(files: SheetFiles) -> None:
    """REQ-SHT-002: every name non-empty with no folder, a program number of at least 1, and at
    least one compiled file."""
    names = [(field, str(getattr(files, field))) for field in _NAMED]
    names += [(f"nc_files[{i}]", name) for i, name in enumerate(files.nc_files)]
    if files.program_number < 1:
        raise ValueError(f"{PREFIX}files.program_number: {files.program_number} is below 1")
    if not files.nc_files:
        raise ValueError(f"{PREFIX}files.nc_files: no compiled file")
    for field, name in names:
        if name == "" or "/" in name or "\\" in name:
            raise ValueError(f"{PREFIX}files.{field}: {name!r} is empty or holds a folder")


def _tool_and_point(job: JobData, operation: Operation) -> tuple[FlatEndMill, MeasurementPoint]:
    for tool in job.tools:
        for point in tool.points if tool.number == operation.tool_number else ():
            if point.number == operation.point_number:
                return tool, point
    where = f"T{operation.tool_number} with point {operation.point_number}"
    raise ValueError(f"{PREFIX}operation {operation.name!r}: the job has no tool {where}")


def _check_names(job: JobData, cl: ClData) -> None:
    planned = job.setup.operations
    for index, (written, operation) in enumerate(zip(cl.operations, planned, strict=False)):
        if written.header.name != operation.name:
            name = written.header.name
            raise ValueError(
                f"{PREFIX}operation {name!r}: name: the job's operation {index} is "
                f"{operation.name!r}"
            )
    if len(cl.operations) != len(planned):
        counts = f"{len(cl.operations)} in the record, {len(planned)} in the job"
        raise ValueError(f"{PREFIX}operations: {counts}")


def check_agreement(job: JobData, cl: ClData) -> tuple[Planned, ...]:
    """REQ-SHT-001: the record's work offset, operations by name and order, and each header's
    tool, point, a and spindle speed are the job's; returns the job's operation, tool and point
    for each of the record's operations, in program order."""
    if cl.work_offset != job.setup.work_offset:
        offsets = f"{cl.work_offset} in the record, {job.setup.work_offset} in the job"
        raise ValueError(f"{PREFIX}work_offset: {offsets}")
    _check_names(job, cl)
    found: list[Planned] = []
    for written, operation in zip(cl.operations, job.setup.operations, strict=True):
        header = written.header
        tool, point = _tool_and_point(job, operation)
        pairs = (
            ("tool_number", header.tool_number, operation.tool_number),
            ("point_number", header.point_number, operation.point_number),
            ("axial_offset_mm", header.axial_offset_mm, point.axial_offset_mm),
            ("spindle_rpm", header.spindle_rpm, operation.spindle_rpm),
        )
        for field, in_record, in_job in pairs:
            if in_record != in_job:  # exact; -0.0 equals 0.0 (DEC-CL-004)
                raise ValueError(
                    f"{PREFIX}operation {header.name!r}: {field}: {in_record!r} in the record, "
                    f"{in_job!r} in the job"
                )
        found.append((operation, tool, point))
    return tuple(found)
