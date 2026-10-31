# SPDX-License-Identifier: Apache-2.0
"""Reading the job file: UTF-8 JSON holding one object, repeated keys kept, no `NaN` and no
infinite number (REQ-JOB-002; DEC-JOB-003)."""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from splintercam.foundation import Diagnostic, Result, Severity


@dataclass(frozen=True, slots=True)
class JsonObject:
    """A JSON object: its (key, value) pairs in file order, a repeated key kept each time."""

    pairs: tuple[tuple[str, object], ...]

    def get(self, key: str) -> object:
        """The first value of `key`; None when it is absent or null."""
        return next((value for name, value in self.pairs if name == key), None)


def _finite(text: str) -> float:
    # The hook of NaN, the infinities and every float: one beyond the double range reads as inf.
    if not math.isfinite(value := float(text)):
        raise ValueError(text)
    return value


def _finite_int(text: str) -> int:
    # An int that reads as an infinite double is no number model can take (REQ-JOB-002); the
    # same rule as the second pass's, so both agree on the place.
    if not math.isfinite(float(text)):
        raise ValueError(text)
    return int(text)


def depth(value: object) -> int:
    """How deeply arrays and objects nest in `value`, 0 for a plain value; without recursion."""
    deepest, stack = 0, [(value, 1)]
    while stack:
        item, level = stack.pop()
        if isinstance(item, JsonObject | list):
            deepest = max(deepest, level)
            items: list[object] = (
                [v for _, v in item.pairs]
                if isinstance(item, JsonObject)
                else cast("list[object]", item)
            )
            stack += ((child, level + 1) for child in items)
    return deepest


# A JSON string, or a number or constant: a pass after Python's json stopped on one finds it
# (RFC 8259 has no NaN or infinities; DEC-JOB-003).
_TOKENS = re.compile(r'"(?:[^"\\]|\\.)*"|-?(?:Infinity|NaN)|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?')


def _where(text: str, at: int) -> str:
    # 1-based, as json.JSONDecodeError counts lines and columns.
    return f"line {text.count('\n', 0, at) + 1}, column {at - text.rfind('\n', 0, at)}"


def _not_finite_at(text: str) -> int:
    # json read the text up to a number it refused: NaN, an infinity or one beyond the double
    # range (as 1e400, or an int over its digit limit, which is beyond it too).
    tokens = (m for m in _TOKENS.finditer(text) if m.group()[0] != '"')
    return next((m.start() for m in tokens if not math.isfinite(float(m.group()))), 0)


def _invalid(where: str, message: str, code: str = "JOB_FILE_INVALID") -> Result[JsonObject]:
    return Result(None, (Diagnostic(code, Severity.ERROR, message, where),))


def read_json(path: Path) -> Result[JsonObject]:
    """The job file's object, or `JOB_FILE_UNREADABLE` or `JOB_FILE_INVALID`.

    Implements: REQ-JOB-002."""
    try:
        data = path.read_bytes()
    except OSError as error:
        message = f"cannot read the job file: {error.strerror or error}"
        return _invalid(str(path), message, "JOB_FILE_UNREADABLE")
    try:
        text = data.decode("utf-8-sig")  # a byte-order mark is accepted (DEC-JOB-003)
    except UnicodeDecodeError as error:
        head = data[: error.start].decode("utf-8-sig")
        return _invalid(_where(head, len(head)), "the job file is not UTF-8")
    return _parse(text)


def _parse(text: str) -> Result[JsonObject]:
    try:
        value = json.loads(text, object_pairs_hook=lambda pairs: JsonObject(tuple(pairs)),
                           parse_constant=_finite, parse_float=_finite,
                           parse_int=_finite_int)  # fmt: skip
    except json.JSONDecodeError as error:
        return _invalid(f"line {error.lineno}, column {error.colno}", f"not JSON: {error.msg}")
    except RecursionError:
        return _invalid("line 1, column 1", "arrays or objects nested too deeply")
    except ValueError:  # from the hooks, or an int beyond the digit limit of Python's json
        message = "NaN and infinite numbers are not JSON (RFC 8259)"
        return _invalid(_where(text, _not_finite_at(text)), message)
    if not isinstance(value, JsonObject):
        return _invalid("line 1, column 1", "the job file holds no JSON object")
    return Result(value)
