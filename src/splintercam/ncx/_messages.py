# SPDX-License-Identifier: Apache-2.0
"""`ncx`'s stderr as diagnostics, each at the operation its line belongs to (REQ-NCX-020 to
022, 025; research 27, The NCX writer and the `ncx` call)."""

import bisect
import re

from splintercam.foundation import Diagnostic, Severity

from ._types import NcxCall, NcxSection, NcxStep

# Research 27: `file(line): SEVERITY CODE: message`; the greedy file takes the last `(digits):`
# before the severity, so a path with `(x86)` or `(2)` in it stays whole.
_MESSAGE = re.compile(
    r"(?P<file>.*)\((?P<line>\d+)\): (?P<severity>ERROR|WARNING|INFO) (?P<code>\S+): (?P<text>.*)"
)
_ROUNDED = "CMP020"  # research 26, Checked condition 3: a value rounded to the machine


def _operation(line: int, sections: tuple[NcxSection, ...]) -> str:
    index = bisect.bisect_right([s.first_line for s in sections], line) - 1
    if index >= 0 and line <= sections[index].last_line:
        return sections[index].operation
    return "program"


def read_messages(
    step: NcxStep, stderr: str, call: NcxCall, sections: tuple[NcxSection, ...]
) -> list[Diagnostic]:
    """`step`'s stderr lines in the order printed; in `compile`, the CMP020s as one
    `NCX_ROUNDED` per location at the place of its first, and any other WARNING or unread line
    followed, at the end, by `NCX_STRICT_FAILED` (DEC-NCX-006, 014)."""
    found: list[Diagnostic] = []
    rounded: dict[str, tuple[int, int]] = {}  # location: (index in found, count)
    ours: dict[str, bool] = {}  # file as printed: is it `ncx_file` (DEC-NCX-014 (d))
    strict = False
    for raw in stderr.splitlines():
        match = _MESSAGE.fullmatch(raw)
        if match is None:
            if raw.strip():
                where = f"ncx {step.value}"
                found.append(Diagnostic("NCX_OUTPUT_UNREAD", Severity.WARNING, raw, where))
                strict = strict or step is NcxStep.COMPILE  # DEC-NCX-014 (e): fail closed
            continue
        file, code, text = match["file"], match["code"], match["text"]
        if file not in ours:
            # ncx runs in work_dir: a relative name is relative to it.
            ours[file] = (call.work_dir / file).resolve() == call.ncx_file.resolve()
        if ours[file]:
            location = _operation(int(match["line"]), sections)
        else:  # the machine file or another input: no operation (REQ-NCX-021)
            location, text = f"ncx {step.value}", f"{file}: {text}"
        severity = Severity[match["severity"]]
        warning = step is NcxStep.COMPILE and severity is Severity.WARNING
        if warning and code == _ROUNDED:  # another severity stays as ncx gave it
            index, count = rounded.get(location, (len(found), 0))
            if count == 0:
                found.append(Diagnostic("NCX_ROUNDED", Severity.INFO, "", location))
            rounded[location] = (index, count + 1)
            continue
        strict = strict or warning
        found.append(Diagnostic(code, severity, text, location))
    for location, (index, count) in rounded.items():
        message = f"{count} values rounded to the machine's decimals ({_ROUNDED}, D-149)"
        found[index] = Diagnostic("NCX_ROUNDED", Severity.INFO, message, location)
    if strict:
        message = (
            f"ncx compile reported a warning other than {_ROUNDED} or an unread line; "
            "it fails as under --strict"
        )
        found.append(Diagnostic("NCX_STRICT_FAILED", Severity.ERROR, message, "ncx compile"))
    return found
