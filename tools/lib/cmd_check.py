# SPDX-License-Identifier: Apache-2.0
"""tools/check [--json]: format check, lint, size, build and tests; must pass before a task is done.

First version (plan 0001, step 1): it runs the whole test suite, not only the changed modules.
arch-check, trace-check and licence-check are not written yet; they are reported as skipped.
"""

import argparse
import sys
from collections.abc import Sequence

from cmd_build import build_step
from cmd_format import all_files, format_steps
from cmd_lint import lint_steps
from cmd_size_check import size_check_step
from runner import Status, StepResult, UsageError, finish, run_step, skip, usage_error

NOT_WRITTEN_YET = ("arch-check", "trace-check", "licence-check")


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="tools/check", description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the result as one JSON line")
    args = parser.parse_args(argv)
    try:
        # Build first: it syncs the tools to uv.lock and refreshes compile_commands.json.
        build = build_step()
        results: list[StepResult] = [build]
        results += format_steps(all_files(), check=True)
        results += lint_steps(None)
        results.append(size_check_step())
        if build.status is Status.PASS:
            results.append(run_step("pytest", ["pytest", "-q"], reproduce="uv run pytest"))
        else:
            results.append(skip("pytest", "build failed"))
        results += [skip(name, "not written yet, plan 0001") for name in NOT_WRITTEN_YET]
        return finish("check", results, as_json=args.json)
    except UsageError as error:
        return usage_error("check", error)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
