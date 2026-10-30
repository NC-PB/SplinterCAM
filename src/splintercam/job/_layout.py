# SPDX-License-Identifier: Apache-2.0
"""The job file's layout, version 1, checked depth-first in key order (REQ-JOB-003 to 009, 020),
and `model`'s types built from it with every value as read (REQ-JOB-006; DEC-JOB-003)."""

import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from splintercam.foundation import Diagnostic, Result, Severity
from splintercam.io import DrawingUnit
from splintercam.model import FlatEndMill, JobData, MeasurementPoint, Operation, Setup, StockBox
from splintercam.ncx import ProgramInfo

from ._json import JsonObject, read_json

# A key's layout: a value, an array of values, `parameters` (an object passed as read), an
# object of `Fields`, or an array of such objects, `(Fields,)`.
LEAF, ARRAY, PAIRS = "a value", "an array", "an object"


@dataclass(frozen=True, slots=True)
class Fields:
    """An object's keys in layout order, each with its layout, and which may be left out."""

    keys: tuple[tuple[str, "Fields | tuple[Fields] | str"], ...]
    optional: frozenset[str] = frozenset()


_POINT = Fields((("axial_offset_mm", LEAF), ("register_radius_mm", LEAF)))
_TOOL = Fields((("number", LEAF), ("type", LEAF), ("diameter_mm", LEAF), ("flute_length_mm", LEAF),
                ("points", (_POINT,))), frozenset({"points"}))  # fmt: skip
_OPERATION = Fields((("name", LEAF), ("strategy", LEAF), ("tool", LEAF), ("point", LEAF),
                     ("spindle_rpm", LEAF), ("tol_mm", LEAF), ("parameters", PAIRS)),
                    frozenset({"point", "parameters"}))  # fmt: skip
_LAYOUT = Fields((
    ("format", LEAF), ("version", LEAF),
    ("part", Fields((("dxf", LEAF), ("layer", LEAF), ("unit", LEAF)),
                    frozenset({"layer", "unit"}))),
    ("tools", (_TOOL,)), ("stock", Fields((("min_mm", ARRAY), ("max_mm", ARRAY)))),
    ("setup", Fields((("work_offset", LEAF),))), ("operations", (_OPERATION,)),
    ("program", Fields((("name", LEAF), ("number", LEAF)))), ("machine", LEAF),
))  # fmt: skip
_UNITS = {"mm": DrawingUnit.MILLIMETRE, "inch": DrawingUnit.INCH}

type Check = Callable[[object, JsonObject], tuple[str, str] | None]


@dataclass(frozen=True, slots=True)
class JobFile:
    """What stage 1 read: the job's data for `model`, the part, the program and the paths."""

    data: JobData
    dxf: Path
    layer: str | None
    unit: DrawingUnit | None
    program: ProgramInfo
    machine: Path
    ncx: Path | None  # the executable, None when none is on the PATH


def absolute(path: Path) -> Path:
    """`path` against the current folder, `..` taken out, links kept."""
    return Path(os.path.normpath(path.absolute()))


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _named(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _value(ok: bool, what: str) -> tuple[str, str] | None:
    return None if ok else ("JOB_VALUE_INVALID", f"must be {what}")


def _checks(machine: Path | None) -> Mapping[str, Check]:
    # The values model does not see (REQ-JOB-007 to 009), keyed by their path without indexes.
    def machine_found(value: object, _: JsonObject) -> tuple[str, str] | None:
        if not _named(value):
            return _value(False, "a non-empty string")
        if machine is None or not machine.is_file():
            return ("JOB_MACHINE_NOT_FOUND", f"the machine file {machine} is not a file")
        return None

    def tool_type(value: object, tool: JsonObject) -> tuple[str, str] | None:
        text = f"tool T{tool.get('number')}: type {value!r}; the slice has flat_end_mill only"
        return None if value == "flat_end_mill" else ("JOB_TOOL_TYPE_UNSUPPORTED", text)

    return {
        "part.dxf": lambda v, _: _value(_named(v), "a non-empty string"),
        "part.layer": lambda v, _: _value(isinstance(v, str), "a string"),
        "part.unit": lambda v, _: _value(v in _UNITS, '"mm" or "inch"'),
        "tools.type": tool_type,
        "program.name": lambda v, _: _value(isinstance(v, str), "a string"),
        "program.number": lambda v, _: _value(_is_int(v), "an int"),
        "machine": machine_found,
    }


class _Walk:
    """Stage 1's diagnostics in the order of REQ-JOB-020."""

    def __init__(self, checks: Mapping[str, Check]) -> None:
        self.out: list[Diagnostic] = []
        self.checks = checks

    def error(self, code: str, message: str, path: str) -> None:
        self.out.append(Diagnostic(code, Severity.ERROR, f"{path}: {message}", path))

    def container(self, value: object, layout: "Fields | tuple[Fields] | str", path: str,
                  kind: str) -> None:  # fmt: skip
        wanted = JsonObject if isinstance(layout, Fields) or layout == PAIRS else list
        if not isinstance(value, wanted):
            name = "an object" if wanted is JsonObject else "an array"
            self.error("JOB_STRUCTURE_INVALID", f"must be {name}", path)
        elif isinstance(layout, Fields) and isinstance(value, JsonObject):
            self.fields(value, layout, path, kind)
        elif isinstance(layout, tuple):
            for index, item in enumerate(cast("list[object]", value), 1):
                self.container(item, layout[0], f"{path}[{index}]", kind)

    def fields(self, value: JsonObject, layout: Fields, path: str, kind: str) -> None:
        names = [key for key, _ in value.pairs]
        for key, spec in layout.keys:
            here, generic = (f"{path}.{key}", f"{kind}.{key}") if path else (key, key)
            given = value.get(key)
            if names.count(key) > 1:
                continue  # one diagnostic per key: JOB_KEY_REPEATED below (DEC-JOB-009)
            if key in layout.optional and given is None:
                continue  # absent and null mean the same (DEC-JOB-003)
            if key not in names or (given is None and spec != LEAF):
                self.error("JOB_KEY_MISSING", "is required", here)  # DEC-JOB-009
            elif spec != LEAF:
                self.container(given, spec, here, generic)
            elif (check := self.checks.get(generic)) and (found := check(given, value)):
                self.error(*found, here)
        known = {key for key, _ in layout.keys}
        for key in sorted({n for n in names if n not in known or names.count(n) > 1}):
            here = f"{path}.{key}" if path else key
            if key not in known:
                self.error("JOB_KEY_UNKNOWN", "is not a key of the job file, version 1", here)
            else:
                self.error("JOB_KEY_REPEATED", f"is given {names.count(key)} times", here)


def _plain(value: object) -> Any:
    # Arrays as tuples (REQ-JOB-006); an object in a value's place as a dict, for model's message.
    if isinstance(value, list):
        return tuple(_plain(item) for item in cast("list[object]", value))
    return dict(value.pairs) if isinstance(value, JsonObject) else value


def _get(owner: JsonObject, key: str) -> Any:
    return _plain(owner.get(key))


def _tool(tool: JsonObject) -> FlatEndMill:
    number, diameter, flutes = (_get(tool, k) for k in ("number", "diameter_mm", "flute_length_mm"))
    if (points := tool.get("points")) is None:
        return FlatEndMill(number, diameter, flutes)  # the tip alone, model.TIP
    taken = tuple(MeasurementPoint(k, _get(p, "axial_offset_mm"), _get(p, "register_radius_mm"))
                  for k, p in enumerate(cast("list[JsonObject]", points), 1))  # fmt: skip
    return FlatEndMill(number, diameter, flutes, taken)


def _operation(op: JsonObject) -> Operation:
    parameters = cast("JsonObject | None", op.get("parameters"))
    pairs = () if parameters is None else tuple((k, _plain(v)) for k, v in parameters.pairs)
    point = _get(op, "point")
    return Operation(_get(op, "name"), _get(op, "strategy"), _get(op, "tool"),
                     _get(op, "spindle_rpm"), _get(op, "tol_mm"), pairs,
                     1 if point is None else point)  # fmt: skip


def _job_file(top: JsonObject, folder: Path, machine: Path, ncx: Path | None) -> JobFile:
    part, stock, program = (cast("JsonObject", top.get(k)) for k in ("part", "stock", "program"))
    operations = tuple(_operation(op) for op in cast("list[JsonObject]", top.get("operations")))
    stock_box = StockBox(_get(stock, "min_mm"), _get(stock, "max_mm"))
    setup = Setup(_get(cast("JsonObject", top.get("setup")), "work_offset"), stock_box, operations)
    data = JobData(tuple(_tool(tool) for tool in cast("list[JsonObject]", top.get("tools"))), setup)
    unit = None if (given := part.get("unit")) is None else _UNITS[cast("str", given)]
    program_info = ProgramInfo(_get(program, "name"), _get(program, "number"))
    dxf = absolute(folder / _get(part, "dxf"))
    return JobFile(data, dxf, _get(part, "layer"), unit, program_info, machine, ncx)


def _ncx(given: Path | None) -> Path | None:
    # REQ-JOB-009, 017: the executable given, else `ncx` on the PATH; None when there is none.
    found = shutil.which("ncx") if given is None else given
    return None if found is None else absolute(Path(found))


def read_job_file(job_file: Path, machine_file: Path | None, ncx_executable: Path | None
                  ) -> Result[JobFile]:  # fmt: skip
    """Stage 1: the job file read and its structure checked, the paths resolved and named.

    Implements: REQ-JOB-002 to 009, REQ-JOB-020."""
    read = read_json(job_file)
    if (top := read.value) is None:
        return Result(None, read.diagnostics)
    form, version = top.get("format"), top.get("version")
    if form != "splintercam-job" or not _is_int(version) or version != 1:
        message = (f"format {form!r}, version {version!r}: this SplinterCAM reads format "
                   "'splintercam-job', version 1")  # fmt: skip
        return Result(None, (Diagnostic("JOB_FORMAT_UNSUPPORTED", Severity.ERROR, message),))
    folder = absolute(job_file).parent
    machine, given = top.get("machine"), machine_file
    if given is None and _named(machine):
        given = folder / cast("str", machine)
    machine_path = None if given is None else absolute(given)
    ncx = _ncx(ncx_executable)
    walk = _Walk(_checks(machine_path))
    walk.fields(top, _LAYOUT, "", "")
    inputs = (
        f"machine file {machine_path or 'none'}; {f'ncx {ncx}' if ncx else 'no ncx on the PATH'}"
    )
    diagnostics = (*walk.out, Diagnostic("JOB_INPUTS", Severity.INFO, inputs))
    if walk.out or machine_path is None:
        return Result(None, diagnostics)
    return Result(_job_file(top, folder, machine_path, ncx), diagnostics)
