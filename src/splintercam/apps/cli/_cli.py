# SPDX-License-Identifier: Apache-2.0
"""`splintercam run`: the arguments, one `run_job` call, the text or JSON report and the exit
code (SPEC.md; feature map, section 1; research 27, Exit codes)."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from splintercam.job import Diagnostic, JobReport, Severity, run_job

# The input could not be read at all: 2, as `ncx` exits for unreadable input or a missing
# machine file (research 27, Exit codes; DEC-CLI-002).
_UNREADABLE = frozenset({"JOB_FILE_UNREADABLE", "DXF_UNREADABLE", "JOB_MACHINE_NOT_FOUND"})
# One diagnostic per line, as `NCX_OUTPUT_UNREAD` holds ncx's text verbatim: the backslash and
# every character that breaks or hides a line but tab escaped (DEC-CLI-001, 003).
_CONTROLS = (*range(0x20), 0x7F, *range(0x80, 0xA0), 0x2028, 0x2029)
_ESCAPES = {c: f"\\x{c:02x}" if c < 0x100 else f"\\u{c:04x}" for c in _CONTROLS if c != 0x09} | {
    ord("\\"): "\\\\", ord("\n"): "\\n", ord("\r"): "\\r"}  # fmt: skip
_AFTER_A_FAILED_RUN = (
    "exit 0: a usable run, its files on stdout; 1: an error, a cancel or, with --strict, a "
    "warning (the NC program then withheld); 2: unreadable input. After 1 or 2, take no file "
    "from the output folder: the files left there are named by FILES_LEFT (AQ-040)."
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="splintercam", description="SplinterCAM's command line.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    run = commands.add_parser("run", help="run a job file to the NCX file and the NC program",
                              epilog=_AFTER_A_FAILED_RUN)  # fmt: skip
    run.add_argument("job_file", metavar="JOB_FILE", type=Path, help="the job file (JSON)")
    run.add_argument("--output", required=True, type=Path, metavar="DIR",
                     help="the output folder, new or empty")  # fmt: skip
    run.add_argument("--ncx", type=Path, metavar="PATH", help="the ncx executable (default: PATH)")
    run.add_argument("--machine", type=Path, metavar="PATH",
                     help="the machine file, instead of the job's")  # fmt: skip
    run.add_argument("--strict", action="store_true",
                     help="a warning fails the run: exit 1, no NC program")  # fmt: skip
    run.add_argument("--json", action="store_true", dest="as_json",
                     help="print one JSON object on stdout")  # fmt: skip
    return parser


def exit_code(report: JobReport, strict: bool) -> int:
    """0 a usable run, 1 an error, a cancel or (strict) a warning, 2 unreadable input
    (REQ-CLI-005; DEC-CLI-002). INFO never changes it: the codes of 2 count as errors only."""
    if any(d.code in _UNREADABLE and d.severity is Severity.ERROR for d in report.diagnostics):
        return 2
    warned = strict and any(d.severity is Severity.WARNING for d in report.diagnostics)
    return 0 if report.ok and not warned else 1


def _line(d: Diagnostic) -> str:
    where = "" if d.location is None else f" {d.location.translate(_ESCAPES)}"
    return f"{d.severity.name} {d.code}{where}: {d.message.translate(_ESCAPES)}"


def _print_report(report: JobReport, code: int, as_json: bool) -> None:
    # Files as the result only for a usable run, so a script never takes a failed run's NCX
    # (DEC-CLI-001); after a failed run every file on disk is named as left (AQ-040 (c)).
    usable = code == 0
    ncx_file = str(report.ncx_file.absolute()) if usable and report.ncx_file else None
    nc_files = [str(p.absolute()) for p in report.nc_files] if usable else []
    left = [] if usable else [str(p.absolute()) for p in (report.ncx_file, *report.nc_files) if p]
    if as_json:
        diagnostics = [{"code": d.code, "severity": d.severity.name, "message": d.message,
                        "location": d.location} for d in report.diagnostics]  # fmt: skip
        found = {"diagnostics": diagnostics, "ncx_file": ncx_file, "nc_files": nc_files,
                 "files_left": left, "exit_code": code}  # fmt: skip
        sys.stdout.write(json.dumps(found, sort_keys=True) + "\n")  # ensure_ascii by default
        return
    lines = [_line(d) for d in report.diagnostics]
    if left:  # DEC-CLI-004: one closing line, in the diagnostics' form
        text = f"left on disk, not for the machine: {', '.join(left)}"
        lines.append(_line(Diagnostic("FILES_LEFT", Severity.INFO, text)))
    sys.stderr.writelines(line + "\n" for line in lines)
    sys.stdout.writelines(path + "\n" for path in filter(None, [ncx_file, *nc_files]))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command of `argv` (default: the process's arguments); the exit code. argparse's
    own exits (usage error 2, help 0) are returned, not raised (REQ-CLI-006)."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return int(stop.code or 0)
    # AQ-040 (b): with --strict a warning also withholds the NC program, not only the exit code.
    report = run_job(args.job_file, args.output, ncx_executable=args.ncx, machine_file=args.machine,
                     strict=args.strict)  # fmt: skip
    code = exit_code(report, args.strict)
    _print_report(report, code, args.as_json)
    return code


def entry() -> NoReturn:
    """The `splintercam` console script: `main` with the process's arguments."""
    sys.exit(main())
