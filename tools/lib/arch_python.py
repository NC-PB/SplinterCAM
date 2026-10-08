# SPDX-License-Identifier: Apache-2.0
"""The rules of architecture/modules.yaml on the map itself and on the Python code (plan 0006).

docs/dev/03, Dependency rules: a module imports itself, the modules its `depends_on` names (Peter,
2026-10-08: lower layers included), its own kernel and the external packages allowed to it.
"""

import ast
import graphlib
import sys
from collections.abc import Iterator
from pathlib import Path

from module_map import Module, ModuleMap

PACKAGE = "splintercam"
KERNELS = "_kernels"
STRATEGY = "strategies/"
APPS = "apps/"


def owner(map_: ModuleMap, relative: Path) -> str | None:
    """The module a path below src/splintercam/ belongs to ("strategies/pocket", "geometry2d")."""
    for size in (2, 1):
        name = "/".join(relative.parts[:size])
        if name in map_.modules:
            return name
    return None


def _cycle(map_: ModuleMap) -> list[str]:
    graph = {name: map_.matching(map_.modules[name].depends_on) for name in sorted(map_.modules)}
    try:
        graphlib.TopologicalSorter(graph).prepare()
    except graphlib.CycleError as error:
        return list(reversed(error.args[1]))  # graphlib gives the cycle backwards
    return []


def map_findings(map_: ModuleMap, known_rules: frozenset[str]) -> list[str]:
    """Violations in modules.yaml itself."""
    findings = [
        f"modules.yaml: rule {rule} is not checked by tools/arch-check"
        for rule in map_.rules
        if rule not in known_rules
    ]
    missing = sorted(known_rules - set(map_.rules))
    findings += [f"modules.yaml: rule {rule} is checked but not listed" for rule in missing]
    for module in map_.modules.values():
        findings += _entry_findings(map_, module)
    if cycle := _cycle(map_):
        findings.append(f"modules.yaml: no-cycles: {' -> '.join(cycle)}")
    return findings


def _entry_findings(map_: ModuleMap, module: Module) -> Iterator[str]:
    where = f"modules.yaml: {module.name}"
    for pattern in module.depends_on:
        if not map_.matching([pattern]):
            yield f"{where}: depends_on names no declared module: {pattern}"
    for dep in map_.matching(module.depends_on):
        other = map_.modules[dep]
        if other.layer > module.layer:
            yield f"{where}: lower-layers-only: {dep} is on layer {other.layer}, above"
        if dep.startswith(STRATEGY) and module.name.startswith(STRATEGY):
            yield f"{where}: no-strategy-to-strategy: {dep}"
        if module.name.startswith(APPS) and dep != "job":
            yield f"{where}: apps-use-job-only: {dep}"
    for dep in module.kernel_includes:
        if dep not in map_.matching(module.depends_on) or not map_.modules[dep].kernel:
            yield f"{where}: kernel_includes {dep}: not a kernel module in depends_on"


def _absolute(node: ast.ImportFrom, package: str) -> str:
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = ".".join(parts[: len(parts) - node.level + 1])
    return f"{base}.{node.module}" if node.module else base


def _imports(tree: ast.Module, package: str) -> Iterator[tuple[int, str, str]]:
    """(line, dotted name, the name the code uses for it) of every import; `from a import b`
    gives a.b, and a plain `import a.b` is used as a.b."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name, alias.asname or alias.name
        elif isinstance(node, ast.ImportFrom):
            base = _absolute(node, package)
            for alias in node.names:
                yield node.lineno, f"{base}.{alias.name}", alias.asname or alias.name


def _dotted(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and (base := _dotted(node.value)):
        return f"{base}.{node.attr}"
    return None


def _kernel_uses(tree: ast.Module, aliases: set[str]) -> Iterator[tuple[int, str]]:
    """(line, kernel name) of every `<alias>.<kernel>`; each alias names splintercam._kernels."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and _dotted(node.value) in aliases:
            yield node.lineno, node.attr


def _internal(map_: ModuleMap, module: Module, target: str) -> str | None:
    """The rule an import of module `target` from `module` breaks, or None."""
    if target == module.name or target in map_.matching(module.depends_on):
        return None
    if module.name.startswith(APPS):
        return "apps-use-job-only"
    if target.startswith(STRATEGY) and module.name.startswith(STRATEGY):
        return "no-strategy-to-strategy"
    return "lower-layers-only"


def _external(map_: ModuleMap, module: Module, top: str) -> str | None:
    if top in sys.stdlib_module_names:
        return None
    allowed = map_.external.get(top)
    if allowed is None:
        return f"external-allowlist: {top} is not listed under external"
    if "*" in allowed or module.name in allowed:
        return None
    return f"external-allowlist: {top} is not allowed in {module.name}"


def _kernel_problem(module: Module, kernel: str) -> str | None:
    if kernel == module.name.replace("/", "_"):  # the submodule name (CMakeLists.txt)
        return None
    return f"kernels-private: {module.name} uses kernel {kernel}"


def _import_problem(map_: ModuleMap, module: Module, dotted: str) -> str | None:
    parts = dotted.split(".")
    if parts[0] != PACKAGE:
        return _external(map_, module, parts[0])
    if parts[1:2] == [KERNELS]:
        return _kernel_problem(module, parts[2]) if len(parts) > 2 else None
    target = owner(map_, Path(*parts[1:]))
    if target is None:
        return f"{dotted} is in no module of modules.yaml"
    if problem := _internal(map_, module, target):
        return f"{problem}: {module.name} imports {target}"
    return None


def file_findings(map_: ModuleMap, module: Module, name: str, source: str) -> list[str]:
    """Violations in one Python file of `module`; `name` is its path from src/."""
    tree = ast.parse(source, filename=name)
    imports = list(_imports(tree, ".".join(Path(name).parent.parts)))
    findings = [
        f"{name}:{line}: {problem}"
        for line, dotted, _ in imports
        if (problem := _import_problem(map_, module, dotted))
    ]
    aliases = {alias for _, dotted, alias in imports if dotted == f"{PACKAGE}.{KERNELS}"}
    findings += [
        f"{name}:{line}: {problem}"
        for line, kernel in _kernel_uses(tree, aliases)
        if (problem := _kernel_problem(module, kernel))
    ]
    return findings
