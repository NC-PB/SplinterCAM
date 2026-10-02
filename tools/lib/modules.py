# SPDX-License-Identifier: Apache-2.0
"""Module names and budgets for the tools/ commands, read from architecture/modules.yaml.

Test folders without a module (tests/kernels/ for the build) are accepted too. Only the names and
the `budget` key are read, with patterns instead of a YAML parser, to avoid a dependency;
tools/arch-check will read the whole file.
"""

import re
from pathlib import Path

from runner import ROOT, UsageError

MODULES_YAML = ROOT / "architecture" / "modules.yaml"
# A module entry: two spaces, the name, a colon and an inline mapping ("  geometry2d: { layer: 1").
_MODULE_ENTRY = re.compile(r"^  ([a-z0-9_]+(?:/[a-z0-9_]+)?):\s*\{")
# A module's size budget in NLOC, inside its inline mapping (docs/dev/12, section 3).
_BUDGET = re.compile(r"\bbudget:\s*(\d+)")


def _module_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    in_modules = False
    for line in MODULES_YAML.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith((" ", "#")):
            in_modules = line.startswith("modules:")
        elif in_modules and (match := _MODULE_ENTRY.match(line)):
            entries[match.group(1)] = line
    return entries


def module_budgets() -> dict[str, int | None]:
    """Each declared module's NLOC budget, or None where modules.yaml declares none."""
    budgets: dict[str, int | None] = {}
    for name, line in _module_entries().items():
        match = _BUDGET.search(line)
        budgets[name] = int(match.group(1)) if match else None
    return budgets


def known_modules() -> list[str]:
    test_folders = {
        path.name
        for path in (ROOT / "tests").iterdir()
        if path.is_dir() and not path.name.startswith(("_", "."))
    }
    return sorted(_module_entries().keys() | test_folders)


def check_module(name: str) -> None:
    if name not in known_modules():
        raise UsageError(f"unknown module {name!r}; known: {', '.join(known_modules())}")


def module_paths(name: str) -> list[Path]:
    """The source and test folders of a module that exist."""
    candidates = (ROOT / "src" / "splintercam" / name, ROOT / "tests" / name)
    return [path for path in candidates if path.is_dir()]
