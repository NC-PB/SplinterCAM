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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="splintercam", description="SplinterCAM's command line.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    run = commands.add_parser("run", help="run a job file to the NCX file and the NC program")
    run.add_argument("job_file", metavar="JOB_FILE", type=Path, help="the job file (JSON)")
    run.add_argument("--output", required=True, type=Path, metavar="DIR",
                     help="the output folder, new or empty")  # fmt: skip
    run.add_argument("--ncx", type=Path, metavar="PATH", help="the ncx executable (default: PATH)")
    run.add_argument("--machine", type=Path, metavar="PATH",
                     help="the machine file, instead of the job's")  # fmt: skip
    run.add_argument("--strict", action="store_true", help="exit 1 on a warning")
    run.add_argument("--json", action="store_true", dest="as_json",
                     help="print one JSON object on stdout")  # fmt: skip
    return parser


def exit_code(report: JobReport, strict: bool) -> int:
    """0 a usable run, 1 an error, a cancel or (strict) a warning, 2 unreadable input
    (REQ-CLI-005; DEC-CLI-002). INFO never changes it."""
    if any(d.code in _UNREADABLE for d in report.diagnostics):
        return 2
    warned = strict and any(d.severity is Severity.WARNING for d in report.diagnostics)
    return 0 if report.ok and not warned else 1


def _escape(text: str) -> str:
    # One diagnostic per line: `NCX_OUTPUT_UNREAD` holds ncx's text verbatim (DEC-CLI-001).
    return text.replace("\n", "\\n").replace("\r", "\\r")


def _line(d: Diagnostic) -> str:
    where = "" if d.location is None else f" {_escape(d.location)}"
    return f"{d.severity.name} {d.code}{where}: {_escape(d.message)}"


def _print_report(report: JobReport, code: int, as_json: bool) -> None:
    # Files only for a usable run, so a script never takes a failed run's NCX (DEC-CLI-001).
    usable = code == 0
    ncx_file = str(report.ncx_file.absolute()) if usable and report.ncx_file else None
    nc_files = [str(p.absolute()) for p in report.nc_files] if usable else []
    if as_json:
        diagnostics = [{"code": d.code, "severity": d.severity.name, "message": d.message,
                        "location": d.location} for d in report.diagnostics]  # fmt: skip
        sys.stdout.write(json.dumps({"diagnostics": diagnostics, "ncx_file": ncx_file,
                                     "nc_files": nc_files, "exit_code": code},
                                    sort_keys=True, ensure_ascii=True) + "\n")  # fmt: skip
        return
    sys.stderr.writelines(_line(d) + "\n" for d in report.diagnostics)
    sys.stdout.writelines(path + "\n" for path in filter(None, [ncx_file, *nc_files]))


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command of `argv` (default: the process's arguments); the exit code. argparse's
    own exits (usage error 2, help 0) are returned, not raised (REQ-CLI-006)."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return int(stop.code or 0)
    report = run_job(args.job_file, args.output, ncx_executable=args.ncx, machine_file=args.machine)
    code = exit_code(report, args.strict)
    _print_report(report, code, args.as_json)
    return code


def entry() -> NoReturn:
    """The `splintercam` console script: `main` with the process's arguments."""
    sys.exit(main())
