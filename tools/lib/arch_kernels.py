# SPDX-License-Identifier: Apache-2.0
"""The kernel rules of architecture/modules.yaml on the C++ code (plan 0006; docs/dev/03, rule 3).

C++ lives only in the kernel/ folder of a module declared with `kernel: true`. A quoted include
resolves into the module's own kernel, or to a header another module lists under
`kernel_interface` when that module is in the includer's `kernel_includes`. An angle include is a
C or C++20 standard header or a header of a library listed under `kernel_libraries` for the
module; nanobind only in bindings.cpp. Vendored code in kernel/vendor/ is not scanned (ADR 0009).
"""

import re
from pathlib import Path

from arch_python import owner
from module_map import Module, ModuleMap

# Every C and C++ suffix, so a file CMake would not build is still found outside its place.
CPP_SUFFIXES = frozenset({".cpp", ".hpp", ".c", ".h", ".cc", ".cxx", ".hh", ".hxx", ".inl", ".ipp"})
KERNEL = "kernel"
VENDOR = "vendor"
BINDINGS = "bindings.cpp"
NANOBIND = "nanobind"

_INCLUDE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]')

# The C and C++20 standard headers, with their sources, kept as data next to this file.
STANDARD_HEADERS = frozenset(
    word
    for line in (Path(__file__).parent / "standard-headers.txt").read_text("utf-8").splitlines()
    if not line.startswith("#")
    for word in line.split()
)

# Where each library of kernel_libraries keeps its headers, from each library's documented
# include path. A library listed in modules.yaml but not here fails, so the two stay in step.
LIBRARY_HEADERS: dict[str, tuple[str, ...]] = {
    "clipper2": ("clipper2/",),
    "boost-polygon": ("boost/polygon/",),
    "nanoflann": ("nanoflann.hpp",),
    "eigen": ("Eigen/",),
    NANOBIND: ("nanobind/",),
    "shewchuk-predicates": (),  # vendored; included by a quoted path (ADR 0009)
}


def map_findings(map_: ModuleMap, package: Path) -> list[str]:
    """kernel_libraries without known headers, kernel_interface headers that do not exist."""
    findings = [
        f"modules.yaml: kernel-libraries-only: no header path known for library {name}"
        for name in map_.libraries
        if name not in LIBRARY_HEADERS
    ]
    for module in map_.modules.values():
        for header in module.kernel_interface:
            if not (package / module.name / KERNEL / header).is_file():
                findings.append(f"modules.yaml: {module.name}: kernel_interface {header} not found")
    return findings


def _quoted(map_: ModuleMap, module: Module, path: Path, header: str, package: Path) -> str | None:
    # Relative to the including file: no include directory points into src/ (CMakeLists.txt).
    target, root = (path.parent / header).resolve(), package.resolve()
    if not target.is_file():
        return f"cannot resolve {header}"
    if not target.is_relative_to(root):
        return f"kernels-private: {header} lies outside src/splintercam/"
    relative = target.relative_to(root)
    other = owner(map_, relative)
    if other is None or relative.relative_to(other).parts[:1] != (KERNEL,):
        return f"kernels-private: {header} is not in a module's kernel/ folder"
    inside = relative.relative_to(Path(other) / KERNEL).as_posix()
    if other == module.name or (
        other in module.kernel_includes and inside in map_.modules[other].kernel_interface
    ):
        return None
    return f"kernels-private: {header} is not {other}'s kernel interface for {module.name}"


def _angle(map_: ModuleMap, module: Module, path: Path, header: str) -> str | None:
    if header in STANDARD_HEADERS:
        return None
    for library, prefixes in LIBRARY_HEADERS.items():
        if any(header.startswith(p) for p in prefixes):
            if library == NANOBIND and path.name != BINDINGS:
                return f"kernel-libraries-only: nanobind only in {BINDINGS}"
            used_by = map_.libraries.get(library, ())
            if "*" in used_by or module.name in used_by:
                return None
            return f"kernel-libraries-only: {library} is not listed for {module.name}"
    return f"kernel-libraries-only: <{header}> is no standard header or listed library"


def file_findings(map_: ModuleMap, path: Path, package: Path) -> list[str]:
    """Violations in one C or C++ file below `package` (src/splintercam/)."""
    relative = path.relative_to(package)
    name = (Path(package.name) / relative).as_posix()
    module_name = owner(map_, relative)
    if module_name is None:
        return [f"{name}: C++ outside a module's kernel/ folder"]
    module = map_.modules[module_name]
    inside = relative.relative_to(module_name).parts
    if inside[:1] != (KERNEL,) or not module.kernel:
        return [f"{name}: C++ outside the kernel/ folder of a kernel: true module"]
    if inside[1:2] == (VENDOR,):
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except ValueError as error:  # bad UTF-8
        return [f"{name}: cannot be read: {error}"]
    findings: list[str] = []
    for line, text in enumerate(lines, start=1):
        if not (match := _INCLUDE.match(text)):
            continue
        kind, header = match.groups()
        if kind == '"':
            problem = _quoted(map_, module, path, header, package)
        else:
            problem = _angle(map_, module, path, header)
        if problem:
            findings.append(f"{name}:{line}: {problem}")
    return findings
