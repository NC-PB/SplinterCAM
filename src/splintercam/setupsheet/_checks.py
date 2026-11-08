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
    names: list[tuple[str, object]] = [(field, getattr(files, field)) for field in _NAMED]
    names += [(f"nc_files[{i}]", name) for i, name in enumerate(files.nc_files)]
    if files.program_number < 1:
        raise ValueError(f"{PREFIX}files.program_number: {files.program_number} is below 1")
    if not files.nc_files:
        raise ValueError(f"{PREFIX}files.nc_files: no compiled file")
    for field, name in names:
        if not isinstance(name, str) or name == "" or "/" in name or "\\" in name:
            raise ValueError(f"{PREFIX}files.{field}: {name!r} is not a name without a folder")


def check_agreement(job: JobData, cl: ClData) -> tuple[Planned, ...]:
    """REQ-SHT-001; returns the job's operation, tool and point (as `model.check_job` checked
    them) for each of the record's operations, in program order."""
    if cl.work_offset != job.setup.work_offset:
        offsets = f"{cl.work_offset} in the record, {job.setup.work_offset} in the job"
        raise ValueError(f"{PREFIX}work_offset: {offsets}")
    planned = job.setup.operations
    if len(cl.operations) != len(planned):
        counts = f"{len(cl.operations)} in the record, {len(planned)} in the job"
        raise ValueError(f"{PREFIX}operations: {counts}")
    found: list[Planned] = []
    for index, (written, operation) in enumerate(zip(cl.operations, planned, strict=True)):
        header = written.header
        if header.name != operation.name:
            raise ValueError(
                f"{PREFIX}operation {header.name!r}: name: the job's operation {index} is "
                f"{operation.name!r}"
            )
        tool = next(t for t in job.tools if t.number == operation.tool_number)
        point = next(p for p in tool.points if p.number == operation.point_number)
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
