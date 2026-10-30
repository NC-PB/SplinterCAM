# SPDX-License-Identifier: Apache-2.0
"""Reading the job file: UTF-8 JSON holding one object, repeated keys kept, no `NaN` and no
infinite number (REQ-JOB-002; DEC-JOB-003)."""

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from splintercam.foundation import Diagnostic, Result, Severity


@dataclass(frozen=True, slots=True)
class JsonObject:
    """A JSON object: its (key, value) pairs in file order, a repeated key kept each time."""

    pairs: tuple[tuple[str, object], ...]

    def keys(self) -> list[str]:
        return [key for key, _ in self.pairs]

    def get(self, key: str) -> object:
        """The first value of `key`; None when it is absent or null."""
        return next((value for name, value in self.pairs if name == key), None)


class _NotFiniteError(ValueError):
    pass


def _refuse_constant(_name: str) -> float:
    raise _NotFiniteError


def _finite(text: str) -> float:
    if math.isinf(value := float(text)):
        raise _NotFiniteError
    return value


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


def _kind(value: object) -> str:
    kinds = ((bool, "a boolean"), (str, "a string"), (list, "an array"), (type(None), "null"))
    return next((name for kind, name in kinds if isinstance(value, kind)), "a number")


def _invalid(where: str, message: str) -> Result[JsonObject]:
    return Result(None, (Diagnostic("JOB_FILE_INVALID", Severity.ERROR, message, where),))


def read_json(path: Path) -> Result[JsonObject]:
    """The job file's object, or `JOB_FILE_UNREADABLE` or `JOB_FILE_INVALID`.

    Implements: REQ-JOB-002."""
    try:
        data = path.read_bytes()
    except OSError as error:
        message = f"cannot read the job file: {error.strerror or error}"
        return Result(None, (Diagnostic("JOB_FILE_UNREADABLE", Severity.ERROR, message,
                                        str(path)),))  # fmt: skip
    try:
        text = data.decode("utf-8-sig")  # a byte-order mark is accepted (DEC-JOB-003)
    except UnicodeDecodeError as error:
        head = data[: error.start].decode("utf-8-sig")
        return _invalid(_where(head, len(head)), "the job file is not UTF-8")
    try:
        value = json.loads(text, object_pairs_hook=lambda pairs: JsonObject(tuple(pairs)),
                           parse_constant=_refuse_constant, parse_float=_finite)  # fmt: skip
    except json.JSONDecodeError as error:
        return _invalid(f"line {error.lineno}, column {error.colno}", f"not JSON: {error.msg}")
    except ValueError:  # _NotFiniteError, or an int beyond the digit limit of Python's json
        message = "NaN and infinite numbers are not JSON (RFC 8259)"
        return _invalid(_where(text, _not_finite_at(text)), message)
    if not isinstance(value, JsonObject):
        return _invalid("line 1, column 1", f"the job file holds {_kind(value)}, not one object")
    return Result(value)
