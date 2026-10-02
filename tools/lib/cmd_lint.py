# SPDX-License-Identifier: Apache-2.0
"""tools/lint [module]: ruff, pyright (strict) and clang-tidy; every warning is an error.

clang-tidy needs the compile_commands.json that tools/build writes into build/<wheel tag>/.
"""

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from modules import check_module, module_paths
from runner import ROOT, StepResult, UsageError, finish, git_files, run_step, skip, usage_error


def kernel_sources(paths: Sequence[Path]) -> list[str]:
    """C++ sources in kernel/ folders under `paths` (src/splintercam/ when `paths` is empty)."""
    roots = paths or [ROOT / "src" / "splintercam"]
    listing = ("ls-files", "--cached", "--others", "--exclude-standard", "--")
    files = [f for root in roots for f in git_files(*listing, str(root))]
    return sorted(
        f.relative_to(ROOT).as_posix()
        for f in files
        if f.suffix == ".cpp" and f.parent.name == "kernel"
    )


def compile_database() -> Path | None:
    """The build folder of the normal build holding the newest compile_commands.json, if any.

    build/sanitize (tools/test --all) is left out: its database carries the sanitizer flags.
    """
    databases = sorted(
        (p for p in ROOT.glob("build/*/compile_commands.json") if p.parent.name != "sanitize"),
        key=lambda p: p.stat().st_mtime,
    )
    return databases[-1].parent if databases else None


def macos_sdk_arguments() -> list[str]:
    """On macOS, point clang-tidy at the SDK. Apple's compiler finds it on its own, and CMake 4 no
    longer writes -isysroot into compile_commands.json, so the PyPI clang-tidy would not find the
    standard library headers."""
    if sys.platform != "darwin":
        return []
    completed = subprocess.run(
        ["xcrun", "--show-sdk-path"], check=False, capture_output=True, text=True, encoding="utf-8"
    )
    if completed.returncode != 0:
        raise UsageError("xcrun --show-sdk-path failed; install the Xcode command line tools")
    return [f"--extra-arg=-isysroot{completed.stdout.strip()}"]


def clang_tidy_step(sources: Sequence[str], reproduce: str) -> StepResult:
    if not sources:
        return skip("clang-tidy", "no kernel sources yet")
    database = compile_database()
    if database is None:
        if sys.platform == "win32":
            # scikit-build-core builds with the Visual Studio generator on Windows, which writes no
            # compile database (CMake: CMAKE_EXPORT_COMPILE_COMMANDS). clang-tidy runs on macOS
            # and Linux, locally and in CI; its findings do not depend on the platform.
            return skip("clang-tidy", "no compile database with the Visual Studio generator")
        raise UsageError("no compile_commands.json under build/; run tools/build first")
    database_arg = database.relative_to(ROOT).as_posix()
    argv = ["clang-tidy", "--quiet", "-p", database_arg, *macos_sdk_arguments(), *sources]
    return run_step("clang-tidy", argv, reproduce=reproduce)


# pyright evaluates `sys.platform` checks statically, so code can type-check on one system and
# fail on another (plan 0001, step 2: a Windows-only error in CI). Check all three everywhere.
PYRIGHT_PLATFORMS = ("Darwin", "Linux", "Windows")


def pyright_steps(targets: Sequence[str], reproduce: str) -> list[StepResult]:
    return [
        run_step(
            f"pyright {platform}",
            ["pyright", "--warnings", "--pythonplatform", platform, *targets],
            reproduce=reproduce,
        )
        for platform in PYRIGHT_PLATFORMS
    ]


def lint_steps(module: str | None) -> list[StepResult]:
    paths = module_paths(module) if module else []
    targets = [p.relative_to(ROOT).as_posix() for p in paths] or ["."]
    reproduce = f"tools/lint {module}" if module else "tools/lint"
    # Without targets pyright checks the include list in pyproject.toml.
    pyright_targets = [t for t in targets if t != "."]
    return [
        run_step("ruff check", ["ruff", "check", *targets], reproduce=reproduce),
        *pyright_steps(pyright_targets, reproduce),
        run_step("clang-tidy config", ["clang-tidy", "--verify-config"], reproduce=reproduce),
        clang_tidy_step(kernel_sources(paths), reproduce),
    ]


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="tools/lint", description=__doc__)
    parser.add_argument("module", nargs="?", help="a module name, for example geometry2d")
    args = parser.parse_args(argv)
    try:
        if args.module is not None:
            check_module(args.module)
        return finish("lint", lint_steps(args.module))
    except UsageError as error:
        return usage_error("lint", error)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
