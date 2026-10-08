# SPDX-License-Identifier: Apache-2.0
"""tools/arch-check: the rules of architecture/modules.yaml (docs/dev/03; plan 0006).

Checks the map itself (declared dependencies, layers, cycles, the rule list), the imports of every
Python file and the includes of every C and C++ file under src/splintercam/. Each violation is
one line, `path:line: rule: what`; any violation fails. Standard library only (Peter,
2026-10-08), so it runs without tools/bootstrap.
"""

import argparse
import sys
import time
from collections.abc import Sequence
from pathlib import Path

import arch_kernels
import arch_python
from module_map import MapError, ModuleMap, read_module_map
from runner import ROOT, Status, StepResult, UsageError, finish, usage_error

KNOWN_RULES = frozenset(
    {
        "lower-layers-only",
        "no-cycles",
        "no-strategy-to-strategy",
        "kernels-private",
        "kernel-libraries-only",
        "external-allowlist",
        "apps-use-job-only",
    }
)


def _python_findings(map_: ModuleMap, path: Path, package: Path) -> list[str]:
    relative = path.relative_to(package)
    name = (Path(package.name) / relative).as_posix()
    if relative == Path("__init__.py"):  # the package's own
        return []
    module = arch_python.owner(map_, relative)
    if module is None:
        return [f"{name}: Python file in no module of modules.yaml"]
    try:
        source = path.read_text(encoding="utf-8-sig")
        return arch_python.file_findings(map_, map_.modules[module], name, source)
    except (SyntaxError, ValueError) as error:  # ValueError: bad UTF-8
        return [f"{name}: cannot be read or parsed: {error}"]


def findings(map_: ModuleMap, package: Path) -> list[str]:
    """Every violation of the map and of the code below `package` (src/splintercam/)."""
    found = arch_python.map_findings(map_, KNOWN_RULES)
    found += arch_kernels.map_findings(map_, package)
    for path in sorted(package.rglob("*")):
        if path.suffix == ".py":
            found += _python_findings(map_, path, package)
        elif path.suffix in arch_kernels.CPP_SUFFIXES:
            found += arch_kernels.file_findings(map_, path, package)
    return found


def arch_check_step() -> StepResult:
    """One step for tools/check; a modules.yaml it cannot read is a usage error."""
    start = time.perf_counter()
    try:
        map_ = read_module_map(ROOT / "architecture" / "modules.yaml")
    except MapError as error:
        raise UsageError(f"architecture/modules.yaml: {error}") from error
    found = findings(map_, ROOT / "src" / "splintercam")
    for finding in found:
        print(f"FAIL  {finding}", flush=True)
    seconds = time.perf_counter() - start
    if found:
        detail = f"{len(found)} violations; reproduce: tools/arch-check"
        return StepResult("arch-check", Status.FAIL, seconds, detail)
    return StepResult("arch-check", Status.PASS, seconds)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="tools/arch-check", description=__doc__)
    parser.parse_args(argv)
    try:
        return finish("arch-check", [arch_check_step()])
    except UsageError as error:
        return usage_error("arch-check", error)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
