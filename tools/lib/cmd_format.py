# SPDX-License-Identifier: Apache-2.0
"""tools/format [--check] [file ...]: format Python with ruff and C++ with clang-format.

Without files it formats the files changed since the last commit, plus new files; with --check it
checks every file and changes nothing. The edit hook calls it for each edited file, so it must stay
fast.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from runner import ROOT, StepResult, UsageError, finish, git_files, run_step, skip, usage_error

PYTHON_SUFFIXES = frozenset({".py", ".pyi"})
CPP_SUFFIXES = frozenset({".cpp", ".hpp", ".h"})


def changed_files() -> list[Path]:
    """Files changed against HEAD, plus untracked files that git does not ignore."""
    changed = git_files("diff", "--name-only", "HEAD")
    untracked = git_files("ls-files", "--others", "--exclude-standard")
    return sorted(set(changed) | set(untracked))


def all_files() -> list[Path]:
    return git_files("ls-files", "--cached", "--others", "--exclude-standard")


def _relative(files: Sequence[Path]) -> list[str]:
    return [path.relative_to(ROOT).as_posix() for path in files]


def format_steps(files: Sequence[Path], *, check: bool) -> list[StepResult]:
    """ruff and clang-format on `files`; with `check`, report instead of rewriting."""
    python = _relative([f for f in files if f.suffix in PYTHON_SUFFIXES])
    cpp = _relative([f for f in files if f.suffix in CPP_SUFFIXES])
    results: list[StepResult] = []
    if not python:
        results.append(skip("ruff format", "no Python files"))
    elif check:
        argv = ["ruff", "format", "--check", "--force-exclude", *python]
        results.append(run_step("ruff format", argv, reproduce="tools/format"))
    else:
        argv = ["ruff", "format", "--force-exclude", *python]
        results.append(run_step("ruff format", argv, reproduce="tools/format"))
        # Import order is part of formatting here; lint reports it too (ruff rule I).
        argv = ["ruff", "check", "--select", "I", "--fix", "--force-exclude", *python]
        results.append(run_step("ruff imports", argv, reproduce="tools/format"))
    if not cpp:
        results.append(skip("clang-format", "no C++ files"))
    elif check:
        argv = ["clang-format", "--dry-run", "--Werror", *cpp]
        results.append(run_step("clang-format", argv, reproduce="tools/format"))
    else:
        results.append(
            run_step("clang-format", ["clang-format", "-i", *cpp], reproduce="tools/format")
        )
    return results


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="tools/format", description=__doc__)
    parser.add_argument("--check", action="store_true", help="check all files, change nothing")
    parser.add_argument(
        "files", nargs="*", type=Path, help="files to format (default: changed files)"
    )
    args = parser.parse_args(argv)
    try:
        if args.files:
            files = [path.resolve() for path in args.files]
            outside = [str(path) for path in files if not path.is_relative_to(ROOT)]
            if outside:
                raise UsageError(f"outside the repository: {', '.join(outside)}")
        else:
            files = all_files() if args.check else changed_files()
        return finish("format", format_steps(files, check=args.check))
    except UsageError as error:
        return usage_error("format", error)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
