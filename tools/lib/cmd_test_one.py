# SPDX-License-Identifier: Apache-2.0
"""tools/test-one <module> [filter]: rebuild if needed, then run the tests in tests/<module>/.

The filter is a pytest -k expression; requirement IDs work as keywords with - or _ (REQ_OFF_003).
"""

import argparse
import sys
from collections.abc import Sequence

from cmd_build import build_step
from modules import check_module
from runner import ROOT, Status, UsageError, finish, run_step, skip, usage_error


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="tools/test-one", description=__doc__)
    parser.add_argument("module", help="a module name, for example geometry2d")
    parser.add_argument("filter", nargs="?", help="pytest -k expression, for example REQ_OFF_003")
    args = parser.parse_args(argv)
    try:
        check_module(args.module)
        tests = ROOT / "tests" / args.module
        if not tests.is_dir():
            raise UsageError(f"no tests for {args.module} yet: tests/{args.module}/ is missing")
        build = build_step()
        results = [build]
        pytest_argv = ["pytest", "-q", f"tests/{args.module}"]
        reproduce = f"tools/test-one {args.module}"
        if args.filter:
            pytest_argv += ["-k", args.filter]
            reproduce += f" {args.filter}"
        if build.status is Status.PASS:
            results.append(run_step("pytest", pytest_argv, reproduce=reproduce))
        else:
            results.append(skip("pytest", "build failed"))
        return finish("test-one", results)
    except UsageError as error:
        return usage_error("test-one", error)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
