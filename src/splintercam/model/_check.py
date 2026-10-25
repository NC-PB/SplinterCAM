# SPDX-License-Identifier: Apache-2.0
"""`check_job`: the one check of a job where it enters, every diagnostic in the order of
REQ-MDL-026 with the locations of REQ-MDL-027 (DEC-MDL-003)."""

import math
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace

from splintercam.foundation import CANCELLED, Context, Diagnostic, Result, Severity, ToleranceSet

from ._types import (
    FlatEndMill,
    JobData,
    MeasurementPoint,
    Operation,
    ParameterDeclaration,
    Setup,
    StockBox,
    in_range,
    range_text,
)

type Declarations = Mapping[str, Sequence[ParameterDeclaration]]
type Entry = tuple[str, float | None]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_float(value: object) -> float | None:
    # REQ-MDL-029: an int must convert to a finite float; float() raises above the largest double.
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    if isinstance(value, int) and abs(value) > sys.float_info.max:
        return None
    return float(value)


def _is_number(value: object) -> bool:
    return _as_float(value) is not None


def _is_corner(value: object) -> bool:
    return isinstance(value, tuple) and len(value) == 3 and all(map(_is_number, value))  # pyright: ignore[reportUnknownArgumentType]


_KINDS: dict[str, Callable[[object], bool]] = {
    "an int": _is_int, "a number": _is_number, "a str": lambda value: isinstance(value, str),
    "a tuple of three numbers": _is_corner,
}  # fmt: skip
_TOOL_FIELDS = {"number": "an int", "diameter_mm": "a number", "flute_length_mm": "a number"}
_POINT_FIELDS = {"number": "an int", "axial_offset_mm": "a number",
                 "register_radius_mm": "a number"}  # fmt: skip
_OP_FIELDS = {"name": "a str", "strategy": "a str", "tool_number": "an int",
              "point_number": "an int", "spindle_rpm": "a number",
              "tol_mm": "a number"}  # fmt: skip
_STOCK_FIELDS = {"min_mm": "a tuple of three numbers", "max_mm": "a tuple of three numbers"}


def _finite_positive(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


class _Checker:
    """Collects the diagnostics of one `check_job` call in the order they are found, which is the
    order of REQ-MDL-026: tools, stock, setup, operations, each element's type errors first."""

    def __init__(self, declarations: Declarations, eps_len_mm: float) -> None:
        self.out: list[Diagnostic] = []
        self.declarations = declarations
        self.eps_len_mm = eps_len_mm
        self.tool_points: dict[int, set[int]] = {}  # T number -> its point numbers (REQ-MDL-014)
        self.op_names: set[str] = set()

    def error(self, code: str, message: str, location: str) -> None:
        self.out.append(Diagnostic(code, Severity.ERROR, message, location))

    def type_error(self, field: str, kind: str, value: object, location: str) -> None:
        message = f"{field} must be {kind}, found {type(value).__name__}"
        self.error("VALUE_TYPE_INVALID", message, location)

    def fields(self, element: object, kinds: Mapping[str, str], location: str) -> set[str]:
        """Report each field not of its kind; return their names, whose other checks are skipped."""
        bad: set[str] = set()
        for field, kind in kinds.items():
            if not _KINDS[kind](value := getattr(element, field)):
                self.type_error(field, kind, value, location)
                bad.add(field)
        return bad

    def elements[T](self, value: object, cls: type[T], field: str, location: str
                    ) -> list[tuple[int, T]]:  # fmt: skip
        """The elements of a tuple field that are `cls`, with their index from 1; anything else is
        reported at the owner (DEC-MDL-009)."""
        if not isinstance(value, tuple):
            self.type_error(field, "a tuple", value, location)
            return []
        good: list[tuple[int, T]] = []
        items: tuple[object, ...] = value  # pyright: ignore[reportUnknownVariableType]
        for index, element in enumerate(items, 1):
            if isinstance(element, cls):
                good.append((index, element))
            else:
                self.type_error(f"{field}[{index - 1}]", f"a {cls.__name__}", element, location)
        return good

    def tool(self, index: int, tool: FlatEndMill) -> None:
        """REQ-MDL-002 to 006, in that order."""
        location = f"tool {index} (T{tool.number})"
        bad = self.fields(tool, _TOOL_FIELDS, location)
        # k is the point's position from 1 (DEC-MDL-009), which equals its number when valid.
        given = self.elements(tool.points, MeasurementPoint, "points", location)
        points = [(k, p, self.fields(p, _POINT_FIELDS, f"{location}, point {k}")) for k, p in given]
        if "number" not in bad and tool.number < 1:
            self.error("TOOL_NUMBER_INVALID", f"tool number {tool.number} is below 1", location)
        dimensions_ok = not bad & {"diameter_mm", "flute_length_mm"}
        for field in ("diameter_mm", "flute_length_mm"):
            if field not in bad and not _finite_positive(value := getattr(tool, field)):
                message = f"{field} is {value!r} mm; it must be finite and above 0"
                self.error("TOOL_DIMENSION_INVALID", message, location)
                dimensions_ok = False
        numbered = [(k, p.number) for k, p, b in points if "number" not in b]
        if "number" not in bad:
            self.tool_number(tool.number, {number for _, number in numbered}, location)
        if tool.points == () or any(k != number for k, number in numbered):
            message = "the measurement points must be numbered 1, 2, ..., n in order (D-155)"
            self.error("TOOL_POINT_NUMBERS", message, location)
        for k, point, point_bad in points if dimensions_ok else []:
            self.point(tool, point, point_bad, f"{location}, point {k}")

    def tool_number(self, number: int, point_numbers: set[int], location: str) -> None:
        if number in self.tool_points:
            self.error("TOOL_NUMBER_DUPLICATE", f"T{number} names an earlier tool", location)
        else:
            self.tool_points[number] = point_numbers

    def point(self, tool: FlatEndMill, point: MeasurementPoint, bad: set[str], location: str
              ) -> None:  # fmt: skip
        a, r = point.axial_offset_mm, point.register_radius_mm
        if "axial_offset_mm" not in bad and not (math.isfinite(a) and a >= 0.0):
            message = f"axial offset a = {a!r} mm lies outside [0, inf) (D-154)"
            self.error("TOOL_POINT_INVALID", message, location)
        elif "axial_offset_mm" not in bad and a > tool.flute_length_mm:
            # DEC-MDL-004: kept, with the shift a typing error would cause (research 26 test 10).
            message = (
                f"point {point.number} lies above the flute length "
                f"{tool.flute_length_mm:g} mm: every Z is output {a:g} mm above the tip"
            )
            warning = Diagnostic("TOOL_POINT_ABOVE_FLUTE", Severity.WARNING, message, location)
            self.out.append(warning)
        if "register_radius_mm" not in bad and not (0.0 <= r <= tool.radius_mm):
            message = f"register radius r = {r!r} mm lies outside [0, {tool.radius_mm:g}] (D-154)"
            self.error("TOOL_POINT_INVALID", message, location)

    def stock(self, stock: StockBox) -> None:
        if self.fields(stock, _STOCK_FIELDS, "stock"):
            return
        for axis, low, high in zip("xyz", stock.min_mm, stock.max_mm, strict=True):
            if not (math.isfinite(low) and math.isfinite(high) and high - low > self.eps_len_mm):
                message = f"the {axis} extent from {low!r} to {high!r} mm is not above eps_len"
                self.error("STOCK_BOX_INVALID", message, "stock")

    def setup(self, setup: Setup) -> list[tuple[int, Operation]]:
        bad = self.fields(setup, {"work_offset": "an int"}, "setup")
        operations = self.elements(setup.operations, Operation, "operations", "setup")
        if not bad and setup.work_offset < 1:
            message = f"work offset {setup.work_offset} is below 1; it is an index, not a G code"
            self.error("SETUP_WORK_OFFSET_INVALID", message, "setup")
        if setup.operations == ():
            self.error("SETUP_NO_OPERATION", "the setup has no operation", "setup")
        return operations

    def operation(self, index: int, op: Operation) -> Operation:
        """Check one operation; return it with its parameters completed (REQ-MDL-024)."""
        location = f"operation {index} ({op.name})"
        bad = self.fields(op, _OP_FIELDS, location)
        entries = self.entries(op.parameters, location)
        self.header(op, bad, location)
        if "strategy" in bad:
            return op
        declared = self.declarations.get(op.strategy)
        if declared is None:
            message = f"no strategy {op.strategy!r} is known; its parameters are not checked"
            self.error("OP_STRATEGY_UNKNOWN", message, location)
            return op
        return replace(op, parameters=self.parameters(entries, declared, location))

    def entries(self, parameters: object, location: str) -> list[Entry]:
        """The (name, value) entries; a value of the wrong type is None (REQ-MDL-029)."""
        entries: list[Entry] = []
        pairs: list[tuple[int, tuple[object, ...]]] = self.elements(
            parameters, tuple, "parameters", location
        )
        for index, pair in pairs:
            if len(pair) != 2 or not isinstance(name := pair[0], str):
                self.type_error(f"parameters[{index - 1}]", "a (str, number) pair", pair, location)
                continue
            if (value := _as_float(pair[1])) is None:
                self.type_error("value", "a number", pair[1], f"{location}, parameter {name}")
            entries.append((name, value))
        return entries

    def header(self, op: Operation, bad: set[str], location: str) -> None:
        """REQ-MDL-012 to 016, in that order."""
        if "name" not in bad:
            if not re.fullmatch(r"[A-Za-z0-9_]+", op.name):
                message = f"name {op.name!r} must be ASCII letters, digits and underscores"
                self.error("OP_NAME_INVALID", message, location)
            if op.name in self.op_names:
                self.error("OP_NAME_DUPLICATE", f"{op.name} names an earlier operation", location)
            self.op_names.add(op.name)
        if "tool_number" not in bad:
            points = self.tool_points.get(op.tool_number)
            if points is None:
                self.error("OP_TOOL_UNKNOWN", f"no tool T{op.tool_number} in the job", location)
            elif "point_number" not in bad and op.point_number not in points:
                message = f"T{op.tool_number} has no measurement point {op.point_number}"
                self.error("OP_POINT_UNKNOWN", message, location)
        if "spindle_rpm" not in bad and not _finite_positive(op.spindle_rpm):
            message = f"spindle speed {op.spindle_rpm!r} 1/min must be finite and above 0"
            self.error("OP_SPINDLE_INVALID", message, location)
        if "tol_mm" not in bad:
            self.tolerance(op.tol_mm, location)

    def tolerance(self, tol_mm: float, location: str) -> None:
        # DEC-MDL-007: the range is foundation's; for_operation raises on a non-finite tol.
        if not math.isfinite(tol_mm):
            self.error("OP_TOL_INVALID", f"tolerance {tol_mm!r} mm is not finite", location)
            return
        for diagnostic in ToleranceSet.for_operation(float(tol_mm)).diagnostics:
            if diagnostic.severity is Severity.ERROR:
                self.out.append(replace(diagnostic, location=location))

    def parameters(self, entries: list[Entry], declared: Sequence[ParameterDeclaration],
                   location: str) -> tuple[tuple[str, float], ...]:  # fmt: skip
        """REQ-MDL-021 to 024: declared names in declaration order, then unknown names sorted."""
        given: dict[str, list[float | None]] = {}
        for name, value in entries:
            given.setdefault(name, []).append(value)
        completed: list[tuple[str, float]] = []
        for declaration in declared:
            at = f"{location}, parameter {declaration.name}"
            values = given.pop(declaration.name, [])
            value = values[0] if values else declaration.default
            if not values and value is None:
                message = (f"{declaration.name} has no value and no default; give it in "
                           f"{declaration.unit.value}")  # fmt: skip
                self.error("PARAM_MISSING", message, at)
            elif values and value is not None and not in_range(value, declaration):
                message = (f"{declaration.name} = {value!r} {declaration.unit.value} lies "
                           f"outside {range_text(declaration)}")  # fmt: skip
                self.error("PARAM_OUT_OF_RANGE", message, at)
            if value is not None:
                completed.append((declaration.name, value))
            self.repeated(declaration.name, values, at)
        for name in sorted(given):
            at = f"{location}, parameter {name}"
            self.error("PARAM_UNKNOWN", f"the strategy declares no parameter {name}", at)
            self.repeated(name, given[name], at)
        return tuple(completed)

    def repeated(self, name: str, values: list[float | None], location: str) -> None:
        if len(values) > 1:
            self.error("PARAM_REPEATED", f"{name} is given {len(values)} times", location)


def check_job(job: JobData, declarations: Declarations, ctx: Context) -> Result[JobData]:
    """Check a job's values once, where they enter, and return it with every operation's
    parameters completed in declaration order.

    `declarations` maps each strategy id to its declarations. Every wrong value gets a diagnostic
    naming its element; the value is present only when none is an error. Repeated declared names
    are a programming error, `ValueError`, raised before anything is checked. Cancelled at entry:
    no value and `CANCELLED` alone.

    Implements: REQ-MDL-002 to 006, 008 to 010, 012 to 016, 019 to 029.
    """
    for strategy, declared in declarations.items():
        names = [declaration.name for declaration in declared]
        if repeated := sorted({name for name in names if names.count(name) > 1}):
            raise ValueError(f"strategy {strategy!r} declares {repeated} more than once")
    if ctx.cancel.is_cancelled:
        return Result(None, (CANCELLED,))
    checker = _Checker(declarations, ctx.tolerances.length_eps_mm)
    for index, tool in checker.elements(job.tools, FlatEndMill, "tools", "job"):
        checker.tool(index, tool)
    checker.stock(job.setup.stock)
    operations = tuple(checker.operation(index, op) for index, op in checker.setup(job.setup))
    diagnostics = tuple(checker.out)
    if any(diagnostic.severity is Severity.ERROR for diagnostic in diagnostics):
        return Result(None, diagnostics)
    return Result(replace(job, setup=replace(job.setup, operations=operations)), diagnostics)
