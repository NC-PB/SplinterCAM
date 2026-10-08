# SPDX-License-Identifier: Apache-2.0
"""Tests of tools/arch-check: the rules of architecture/modules.yaml (plan 0006).

Infrastructure only: no requirement covers the tools, so these tests carry no `req` marker. Each
test writes a small src/splintercam/ tree into a temporary folder and checks it against MAP.
"""

from pathlib import Path

import pytest

from cmd_arch_check import KNOWN_RULES, findings
from module_map import ModuleMap, module_map, parse, read_module_map
from runner import ROOT

RULES = "".join(f"  - {rule}\n" for rule in sorted(KNOWN_RULES))
# [GEO] keeps the offset2d line under the length limit.
MODULES = """
modules:
  foundation: { layer: 0, kernel: false, depends_on: [] }
  geometry2d: { layer: 1, kernel: true, depends_on: [foundation], kernel_interface: [exact.hpp] }
  geometry3d: { layer: 1, kernel: true, depends_on: [foundation] }
  offset2d: { layer: 1, kernel: true, depends_on: [foundation, geometry2d], kernel_includes: [GEO] }
  model: { layer: 2, kernel: false, depends_on: [foundation] }
  strategies/pocket: { layer: 3, kernel: false, depends_on: [foundation, model] }
  strategies/profile: { layer: 3, kernel: false, depends_on: [foundation] }
  job: { layer: 5, kernel: false, depends_on: [foundation, "strategies/*"] }
  apps/cli: { layer: 6, kernel: false, depends_on: [job] }
kernel_libraries:
  clipper2: { used_by: [geometry2d] }
  nanobind: { used_by: ["*"] }
external:
  numpy: { allowed_in: ["*"] }
  cadquery-ocp: { import: OCP, allowed_in: [model] }
""".replace("[GEO]", "[geometry2d]")


def _map(modules: str = MODULES, rules: str = RULES) -> ModuleMap:
    return module_map(parse(f"rules:\n{rules}{modules}"))


def _tree(root: Path, files: dict[str, str]) -> Path:
    package = root / "splintercam"
    for name, text in {"geometry2d/kernel/exact.hpp": "", **files}.items():
        path = package / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return package


def _check(tmp_path: Path, files: dict[str, str], map_: ModuleMap | None = None) -> list[str]:
    return findings(map_ or _map(), _tree(tmp_path, files))


def test_the_repository_passes() -> None:
    map_ = read_module_map(ROOT / "architecture" / "modules.yaml")
    assert findings(map_, ROOT / "src" / "splintercam") == []


def test_allowed_imports_pass(tmp_path: Path) -> None:
    source = """
import math
from collections.abc import Sequence
import numpy
from numpy.typing import NDArray
from splintercam import _kernels
from splintercam.foundation import Context
from . import _area
from ._area import area
_kernels.geometry2d.area()
"""
    files = {
        "__init__.py": "",
        "geometry2d/_area.py": "def area() -> None: ...\n",
        "geometry2d/region.py": source,
        "offset2d/offset.py": "from splintercam.geometry2d import Region\n",
        "job/plan.py": "from splintercam.strategies.pocket import plan\n",
        "apps/cli/main.py": "from splintercam import job\n",
        # An external package allowed to named modules only; a strategy's own kernel by its
        # submodule name (CMakeLists.txt: "/" becomes "_").
        "model/shape.py": "from OCP.TopoDS import TopoDS_Shape\n",
        "strategies/pocket/p.py": "from splintercam import _kernels\n"
        "_kernels.strategies_pocket.f()\n",
    }
    assert _check(tmp_path, files) == []


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    [
        # A lower layer not named in depends_on (Peter, 2026-10-08).
        (
            "model/m.py",
            "import splintercam.geometry2d\n",
            "lower-layers-only: model imports geometry2d",
        ),
        (
            "foundation/f.py",
            "from splintercam.model import M\n",
            "lower-layers-only: foundation imports model",
        ),
        # The same layer only when named.
        (
            "geometry2d/g.py",
            "from splintercam import geometry3d\n",
            "lower-layers-only: geometry2d imports geometry3d",
        ),
        (
            "geometry2d/g.py",
            "from .. import model\n",
            "lower-layers-only: geometry2d imports model",
        ),
        (
            "strategies/pocket/p.py",
            "from splintercam.strategies.profile import x\n",
            "no-strategy-to-strategy: strategies/pocket imports strategies/profile",
        ),
        (
            "apps/cli/c.py",
            "from splintercam.foundation import Context\n",
            "apps-use-job-only: apps/cli imports foundation",
        ),
        ("model/m.py", "from splintercam.cam import x\n", "splintercam.cam.x is in no module"),
    ],
)
def test_an_import_outside_depends_on_fails(
    tmp_path: Path, name: str, source: str, expected: str
) -> None:
    (finding,) = _check(tmp_path, {name: source})
    assert finding.startswith(f"splintercam/{name}:1: ")
    assert expected in finding


@pytest.mark.parametrize(
    "source",
    [
        "from splintercam import _kernels\n_kernels.geometry2d.f()\n",
        "from splintercam import _kernels as k\nk.geometry2d.f()\n",
        "import splintercam._kernels\nsplintercam._kernels.geometry2d.f()\n",
        "from splintercam._kernels import geometry2d\n",
    ],
)
def test_another_modules_kernel_fails(tmp_path: Path, source: str) -> None:
    (finding,) = _check(tmp_path, {"offset2d/o.py": source})
    assert "kernels-private: offset2d uses kernel geometry2d" in finding


def test_another_strategys_kernel_fails(tmp_path: Path) -> None:
    source = "from splintercam import _kernels\n_kernels.strategies_profile.f()\n"
    (finding,) = _check(tmp_path, {"strategies/pocket/p.py": source})
    assert "kernels-private: strategies/pocket uses kernel strategies_profile" in finding


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "from OCP.TopoDS import TopoDS_Shape\n",
            "external-allowlist: OCP is not allowed in geometry2d",
        ),
        ("import requests\n", "external-allowlist: requests is not listed under external"),
        (
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import PySide6\n",
            "external-allowlist: PySide6 is not listed",
        ),
    ],
)
def test_an_external_package_outside_the_allowlist_fails(
    tmp_path: Path, source: str, expected: str
) -> None:
    (finding,) = _check(tmp_path, {"geometry2d/g.py": source})
    assert expected in finding


def test_python_in_no_module_or_unparsable_fails(tmp_path: Path) -> None:
    found = _check(tmp_path, {"stray/s.py": "", "model/bad.py": "def (:\n"})
    assert len(found) == 2
    assert found[0].startswith("splintercam/model/bad.py: cannot be read or parsed")
    assert found[1] == "splintercam/stray/s.py: Python file in no module of modules.yaml"


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        (
            "  core: { layer: 0, kernel: false, depends_on: [model] }",
            "core: lower-layers-only: model is on layer 2",
        ),
        (
            "  core: { layer: 0, kernel: false, depends_on: [cam] }",
            "core: depends_on names no declared module: cam",
        ),
        (
            "  strategies/x: { layer: 3, kernel: false, depends_on: [strategies/pocket] }",
            "strategies/x: no-strategy-to-strategy: strategies/pocket",
        ),
        (
            "  apps/gui: { layer: 6, kernel: false, depends_on: [job, model] }",
            "apps/gui: apps-use-job-only: model",
        ),
        (
            "  core: { layer: 2, kernel: true, depends_on: [], kernel_includes: [geometry2d] }",
            "core: kernel_includes geometry2d: not a kernel module in depends_on",
        ),
        (
            "  core: { layer: 2, kernel: true, depends_on: [foundation],"
            " kernel_includes: [foundation] }",
            "core: kernel_includes foundation: not a kernel module in depends_on",
        ),
        (
            "  a: { layer: 2, kernel: false, depends_on: [b] }\n"
            "  b: { layer: 2, kernel: false, depends_on: [a] }",
            "no-cycles: a -> b -> a",
        ),
    ],
)
def test_a_broken_map_fails(tmp_path: Path, entry: str, expected: str) -> None:
    (finding,) = _check(
        tmp_path, {}, _map(MODULES.replace("kernel_libraries:", f"{entry}\nkernel_libraries:"))
    )
    assert finding.startswith("modules.yaml: ")
    assert expected in finding


def test_the_rule_list_matches_the_tool(tmp_path: Path) -> None:
    rules = RULES.replace("  - no-cycles\n", "  - no-globals\n")
    assert _check(tmp_path, {}, _map(rules=rules)) == [
        "modules.yaml: rule no-globals is not checked by tools/arch-check",
        "modules.yaml: rule no-cycles is checked but not listed",
    ]


def test_allowed_kernel_includes_pass(tmp_path: Path) -> None:
    files = {
        "geometry2d/kernel/area.cpp": '#include "exact.hpp"\n#include <vector>\n#include <cmath>\n'
        "#include <clipper2/clipper.h>\n",
        "geometry2d/kernel/bindings.cpp": "#include <nanobind/nanobind.h>\n",
        "geometry2d/kernel/shewchuk.c": '#include "vendor/predicates.c"\n',
        "geometry2d/kernel/vendor/predicates.c": "#include <sys/time.h>\n",
        "offset2d/kernel/offset.cpp": '#include "../../geometry2d/kernel/exact.hpp"\n',
    }
    assert _check(tmp_path, files) == []


@pytest.mark.parametrize(
    ("name", "include", "expected"),
    [
        ("geometry2d/kernel/a.cpp", "<nanobind/nanobind.h>", "nanobind only in bindings.cpp"),
        (
            "geometry3d/kernel/a.cpp",
            "<clipper2/clipper.h>",
            "clipper2 is not listed for geometry3d",
        ),
        ("geometry2d/kernel/a.cpp", "<Python.h>", "<Python.h> is no standard header"),
        ("geometry2d/kernel/a.cpp", "<TopoDS_Shape.hxx>", "is no standard header"),
        ("geometry2d/kernel/a.cpp", '"missing.hpp"', "cannot resolve missing.hpp"),
        (
            "offset2d/kernel/a.cpp",
            '"../../geometry2d/kernel/grid.hpp"',
            "is not geometry2d's kernel interface",
        ),
        (
            "geometry3d/kernel/a.cpp",
            '"../../geometry2d/kernel/exact.hpp"',
            "is not geometry2d's kernel interface",
        ),
        (
            "offset2d/kernel/a.cpp",
            '"../../geometry2d/kernel/vendor/p.c"',
            "is not geometry2d's kernel interface",
        ),
        ("offset2d/kernel/a.cpp", '"../../geometry2d/g.hpp"', "not in a module's kernel/ folder"),
    ],
)
def test_a_kernel_include_outside_the_rules_fails(
    tmp_path: Path, name: str, include: str, expected: str
) -> None:
    files = {
        "geometry2d/kernel/grid.hpp": "",
        "geometry2d/kernel/vendor/p.c": "",
        "geometry2d/g.hpp": "",
        name: f"// a kernel file\n#include {include}\n",
    }
    found = [f for f in _check(tmp_path, files) if not f.startswith("splintercam/geometry2d/g.hpp")]
    (finding,) = found
    assert finding.startswith(f"splintercam/{name}:2: ")
    assert expected in finding


def test_cpp_outside_a_kernel_fails(tmp_path: Path) -> None:
    files = {"model/kernel/m.cpp": "", "geometry2d/g.cpp": "", "loose.hpp": ""}
    assert _check(tmp_path, files) == [
        "splintercam/geometry2d/g.cpp: C++ outside the kernel/ folder of a kernel: true module",
        "splintercam/loose.hpp: C++ outside a module's kernel/ folder",
        "splintercam/model/kernel/m.cpp: C++ outside the kernel/ folder of a kernel: true module",
    ]


def test_the_map_names_existing_headers_and_known_libraries(tmp_path: Path) -> None:
    modules = MODULES.replace(
        "kernel_interface: [exact.hpp]", "kernel_interface: [exact.hpp, gone.hpp]"
    )
    modules = modules.replace("  nanobind:", "  cgal: { used_by: [geometry2d] }\n  nanobind:")
    assert _check(tmp_path, {}, _map(modules)) == [
        "modules.yaml: kernel-libraries-only: no header path known for library cgal",
        "modules.yaml: geometry2d: kernel_interface gone.hpp not found",
    ]


def test_unreadable_files_fail_and_a_byte_order_mark_is_read(tmp_path: Path) -> None:
    package = _tree(tmp_path, {"model/marked.py": "\ufeffimport math\n"})
    (package / "model" / "bad.py").write_bytes(b"x = '\xff'\n")
    (package / "geometry2d" / "kernel" / "bad.cpp").write_bytes(b"// \xff\n")
    found = findings(_map(), package)
    assert len(found) == 2
    assert found[0].startswith("splintercam/geometry2d/kernel/bad.cpp: cannot be read")
    assert found[1].startswith("splintercam/model/bad.py: cannot be read or parsed")


def test_an_include_outside_the_package_fails(tmp_path: Path) -> None:
    (tmp_path / "outside.hpp").write_text("", encoding="utf-8")
    (finding,) = _check(tmp_path, {"geometry2d/kernel/a.cpp": '#include "../../../outside.hpp"\n'})
    assert "kernels-private: ../../../outside.hpp lies outside src/splintercam/" in finding


def test_every_cpp_suffix_is_placed(tmp_path: Path) -> None:
    found = _check(tmp_path, {"model/a.cc": "", "model/b.inl": ""})
    assert [f.split(":")[0] for f in found] == ["splintercam/model/a.cc", "splintercam/model/b.inl"]
