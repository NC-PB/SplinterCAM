# SPDX-License-Identifier: Apache-2.0
"""`ncx`'s stderr as diagnostics with their operation (REQ-NCX-020 to 022, 025)."""

from pathlib import Path

import pytest

from splintercam.foundation import Diagnostic, Severity
from splintercam.ncx import NcxCall, NcxSection, NcxStep
from splintercam.ncx._messages import read_messages

_NCX = Path("/jobs/Program Files (x86)/RECT(2).ncx")
_MACHINE = "/ncxchange/machines/heidenhain-itnc530.toml"
_CALL = NcxCall(Path("/ncx/ncx"), _NCX.parent, _NCX, Path(_MACHINE), Path("/jobs/out"))
_SECTIONS = (
    NcxSection("operation 1 (A)", 5, 50, 0.001),
    NcxSection("operation 2 (B)", 51, 90, 0.001),
)


def _read(step: NcxStep, *lines: str) -> list[Diagnostic]:
    return read_messages(step, "\n".join(lines) + "\n", _CALL, _SECTIONS)


def _at(line: int, rest: str) -> str:
    return f"{_NCX}({line}): {rest}"


def _strict(step: NcxStep) -> Diagnostic:
    # REQ-NCX-027 (AQ-036 item 4): a warning or an unread line in `format --check` or `check`.
    message = f"ncx {step.value} reported a warning or an unread line; it fails as under --strict"
    return Diagnostic("NCX_STRICT_FAILED", Severity.ERROR, message, f"ncx {step.value}")


@pytest.mark.req("REQ-NCX-020", "REQ-NCX-027")
def test_the_three_severities_are_read() -> None:
    found = _read(
        NcxStep.CHECK,
        _at(7, "ERROR VM440: F on a RAPID"),
        _at(8, "WARNING CMP020: X95.1234567 written as X95.123"),
        _at(9, "INFO VM001: note"),
    )
    assert found == [
        Diagnostic("VM440", Severity.ERROR, "F on a RAPID", "operation 1 (A)"),
        Diagnostic("CMP020", Severity.WARNING, "X95.1234567 written as X95.123", "operation 1 (A)"),
        Diagnostic("VM001", Severity.INFO, "note", "operation 1 (A)"),
        _strict(NcxStep.CHECK),
    ]


@pytest.mark.req("REQ-NCX-020", "REQ-NCX-027")
def test_other_lines_are_kept_verbatim() -> None:
    found = _read(NcxStep.FORMAT, "Unhandled exception: (3): ERROR", "", "   ", "x(1): FATAL A: b")
    assert found == [
        *(
            Diagnostic("NCX_OUTPUT_UNREAD", Severity.WARNING, line, "ncx format")
            for line in ("Unhandled exception: (3): ERROR", "x(1): FATAL A: b")
        ),
        _strict(NcxStep.FORMAT),
    ]


@pytest.mark.req("REQ-NCX-027")
@pytest.mark.parametrize("step", [NcxStep.FORMAT, NcxStep.CHECK])
@pytest.mark.parametrize(
    ("line", "code"),
    [
        (_at(6, "WARNING VM300: unused word"), "VM300"),
        (f"{_NCX}(6,3): warning VM300: x", "NCX_OUTPUT_UNREAD"),
    ],
)
def test_format_and_check_fail_closed(step: NcxStep, line: str, code: str) -> None:
    # Peter, AQ-036 item 4: as compile does (DEC-NCX-014 (e)), whatever the exit code.
    found = _read(step, line, _at(7, "INFO VM001: note"))
    assert [(d.code, d.severity) for d in found] == [
        (code, Severity.WARNING),
        ("VM001", Severity.INFO),
        ("NCX_STRICT_FAILED", Severity.ERROR),
    ]
    assert found[-1] == _strict(step)


@pytest.mark.req("REQ-NCX-027")
@pytest.mark.parametrize("step", [NcxStep.FORMAT, NcxStep.CHECK])
def test_format_and_check_pass_with_errors_and_infos_only(step: NcxStep) -> None:
    found = _read(step, _at(6, "ERROR VM440: x"), _at(7, "INFO VM001: y"), "", "  ")
    assert [d.code for d in found] == ["VM440", "VM001"]


@pytest.mark.req("REQ-NCX-020")
def test_windows_line_ends_are_read() -> None:
    stderr = _at(60, "ERROR VM200: motion before UNITS") + "\r\n"
    found = read_messages(NcxStep.CHECK, stderr, _CALL, _SECTIONS)
    assert found == [Diagnostic("VM200", Severity.ERROR, "motion before UNITS", "operation 2 (B)")]


@pytest.mark.req("REQ-NCX-021")
@pytest.mark.parametrize(
    ("line", "location"),
    [
        (1, "program"),
        (4, "program"),
        (5, "operation 1 (A)"),
        (50, "operation 1 (A)"),
        (51, "operation 2 (B)"),
        (90, "operation 2 (B)"),
        (91, "program"),
    ],
)
def test_the_line_gives_the_operation(line: int, location: str) -> None:
    found = _read(NcxStep.CHECK, _at(line, "ERROR VM200: x"))
    assert [d.location for d in found] == [location]


@pytest.mark.req("REQ-NCX-021", "REQ-NCX-027")
def test_another_file_is_named_and_not_mapped() -> None:
    found = _read(NcxStep.CHECK, f"{_MACHINE}(5): WARNING CFG002: unknown key 'x'")
    assert found == [
        Diagnostic("CFG002", Severity.WARNING, f"{_MACHINE}: unknown key 'x'", "ncx check"),
        _strict(NcxStep.CHECK),
    ]


@pytest.mark.req("REQ-NCX-022", "REQ-NCX-025")
def test_compile_counts_cmp020_per_location() -> None:
    found = _read(
        NcxStep.COMPILE,
        _at(6, "WARNING CMP020: a"),
        _at(60, "INFO CMP001: b"),
        _at(7, "WARNING CMP020: c"),
        _at(61, "WARNING CMP020: d"),
        _at(8, "WARNING CMP020: e"),
    )
    assert [(d.code, d.severity, d.location) for d in found] == [
        ("NCX_ROUNDED", Severity.INFO, "operation 1 (A)"),
        ("CMP001", Severity.INFO, "operation 2 (B)"),
        ("NCX_ROUNDED", Severity.INFO, "operation 2 (B)"),
    ]
    assert found[0].message.startswith("3 ")
    assert found[2].message.startswith("1 ")


@pytest.mark.req("REQ-NCX-022")
def test_another_compile_warning_fails_as_strict() -> None:
    found = _read(
        NcxStep.COMPILE,
        _at(6, "WARNING CMP501: NAME is not a valid file name"),
        _at(7, "WARNING CMP020: a"),
    )
    assert [(d.code, d.severity) for d in found] == [
        ("CMP501", Severity.WARNING),
        ("NCX_ROUNDED", Severity.INFO),
        ("NCX_STRICT_FAILED", Severity.ERROR),
    ]
    assert "compile" in found[2].message


@pytest.mark.req("REQ-NCX-020", "REQ-NCX-022")
def test_an_unread_compile_line_fails_as_strict() -> None:
    # DEC-NCX-014 (e): a warning in a form the parser does not know must not pass compile.
    found = _read(NcxStep.COMPILE, f"{_NCX}(6,3): warning CMP501: NAME")
    assert [(d.code, d.severity) for d in found] == [
        ("NCX_OUTPUT_UNREAD", Severity.WARNING),
        ("NCX_STRICT_FAILED", Severity.ERROR),
    ]


@pytest.mark.req("REQ-NCX-022")
def test_a_cmp020_error_is_not_counted() -> None:
    found = _read(NcxStep.COMPILE, _at(6, "ERROR CMP020: beyond the rounding limit"))
    assert [(d.code, d.severity) for d in found] == [("CMP020", Severity.ERROR)]


@pytest.mark.req("REQ-NCX-021")
def test_the_ncx_file_is_found_by_its_resolved_path() -> None:
    roundabout = "/jobs/x/../Program Files (x86)/RECT(2).ncx(7): ERROR VM440: F on a RAPID"
    bare = "RECT(2).ncx(60): ERROR VM440: F on a RAPID"  # relative to the work folder
    found = _read(NcxStep.CHECK, roundabout, bare)
    assert [d.location for d in found] == ["operation 1 (A)", "operation 2 (B)"]


@pytest.mark.req("REQ-NCX-022", "REQ-NCX-027")
def test_cmp020_outside_compile_is_kept() -> None:
    # Kept as ncx reports it (DEC-NCX-014 (c)), and a warning of check: it fails (DEC-NCX-017).
    found = _read(NcxStep.CHECK, _at(6, "WARNING CMP020: a"))
    assert [(d.code, d.severity) for d in found] == [
        ("CMP020", Severity.WARNING),
        ("NCX_STRICT_FAILED", Severity.ERROR),
    ]


@pytest.mark.req("REQ-NCX-025")
def test_messages_keep_the_order_printed() -> None:
    codes = [f"VM{n:03d}" for n in (9, 2, 5, 1)]
    found = _read(NcxStep.CHECK, *(_at(80 - i, f"ERROR {c}: x") for i, c in enumerate(codes)))
    assert [d.code for d in found] == codes
