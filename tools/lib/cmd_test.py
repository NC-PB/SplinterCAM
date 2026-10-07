# SPDX-License-Identifier: Apache-2.0
"""tools/test [--all]: the whole pytest suite; --all also runs it against the sanitizer build.

First version (plan 0001, step 2): tests of changed modules only come later (tools/README.md);
for now this runs everything, like tools/check's pytest step.

--all additionally builds the kernels with AddressSanitizer and UndefinedBehaviorSanitizer
(CMakeLists.txt, SPLINTERCAM_SANITIZE) in a second environment, .venv-sanitize, and runs the whole
suite again with the sanitizer runtime preloaded (docs/dev/04, "C++ kernels"; the libasan and
IREE sanitizer documentation for the preload variables below). On Linux and macOS only; Windows
has no supported sanitizer build (CMakeLists.txt rejects SPLINTERCAM_SANITIZE with MSVC), so --all
reports that step as skipped there.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence

from cmd_build import build_step
from runner import ROOT, Status, StepResult, UsageError, finish, run_step, skip, usage_error

SANITIZE_VENV = ROOT / ".venv-sanitize"
SANITIZE_BUILD_DIR = "build/sanitize"
SANITIZE_REPRODUCE = "tools/test --all"


def _run(argv: Sequence[str], *, env: dict[str, str], label: str) -> tuple[int, float]:
    """Run `argv` from the repository root with `env`; return (exit code, seconds)."""
    executable = shutil.which(argv[0])
    if executable is None:
        raise UsageError(f"{argv[0]} not found; run tools/bootstrap")
    print(f"==> {label}: {' '.join(argv)}", flush=True)
    start = time.perf_counter()
    completed = subprocess.run([executable, *argv[1:]], cwd=ROOT, check=False, env=env)
    return completed.returncode, time.perf_counter() - start


def _asan_runtime_path(compiler: str) -> str | None:
    """Path to the ASan runtime shared library for `compiler` (Linux).

    GCC's runtime is `libasan.so`, found the same way tools/lint finds the macOS SDK: ask the
    compiler itself (`-print-file-name`), since its exact location depends on the installed
    compiler version. Clang instead reports a versioned `libclang_rt.asan-<arch>.so`.
    """
    gcc_style = subprocess.run(
        [compiler, "-print-file-name=libasan.so"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if gcc_style.returncode == 0 and gcc_style.stdout.strip() not in ("", "libasan.so"):
        return gcc_style.stdout.strip()
    version = subprocess.run(
        [compiler, "--version"], check=False, capture_output=True, text=True, encoding="utf-8"
    )
    if "clang" not in version.stdout.lower():
        return None
    clang_style = subprocess.run(
        [compiler, "-print-file-name=libclang_rt.asan-x86_64.so"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    found = clang_style.stdout.strip()
    return found if clang_style.returncode == 0 and found != "libclang_rt.asan-x86_64.so" else None


def _cxx_runtime_path(compiler: str) -> str | None:
    """Path to the C++ runtime `compiler` links (Linux), found like the ASan runtime."""
    completed = subprocess.run(
        [compiler, "-print-file-name=libstdc++.so"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    found = completed.stdout.strip()
    return found if completed.returncode == 0 and found not in ("", "libstdc++.so") else None


def _sanitizer_env() -> dict[str, str] | None:
    """Environment for the sanitizer pytest run, or None if this platform has no runtime to preload.

    ASAN_OPTIONS=detect_leaks=0: CPython itself leaks memory at interpreter shutdown, which would
    otherwise fail every run regardless of the kernels (libasan documentation, LeakSanitizer).
    UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1: stop and print a stack trace on the first
    undefined-behaviour report, so a report fails the step instead of being merely logged
    (IREE's sanitizer documentation, "Using SanitizerRuntimes").
    On Linux the C++ runtime is preloaded after the ASan runtime: Python does not link it, so ASan's
    __cxa_throw interceptor finds no real __cxa_throw when the kernel module loads it later, and
    the first exception a kernel throws aborts ("CHECK failed: ... real___cxa_throw", seen in CI on
    plan 0004, step 3).
    """
    env = dict(os.environ)
    if sys.platform == "darwin":
        completed = subprocess.run(
            ["xcrun", "clang", "-print-file-name=libclang_rt.asan_osx_dynamic.dylib"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        runtime = completed.stdout.strip()
        # -print-file-name echoes the bare name when the library does not exist.
        if completed.returncode != 0 or runtime in ("", "libclang_rt.asan_osx_dynamic.dylib"):
            return None
        env["DYLD_INSERT_LIBRARIES"] = runtime
    elif sys.platform.startswith("linux"):
        compiler = os.environ.get("CXX", "c++")
        runtime = _asan_runtime_path(compiler)
        if runtime is None:
            return None
        cxx_runtime = _cxx_runtime_path(compiler)
        env["LD_PRELOAD"] = runtime if cxx_runtime is None else f"{runtime}:{cxx_runtime}"
    else:
        return None
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
    return env


def _is_instrumented() -> bool:
    """True if the sanitizer environment's kernel module references the ASan runtime.

    A canary: if the SPLINTERCAM_SANITIZE setting were ignored (a cached wheel, a changed build
    option), the tests would run a normal build with the runtime preloaded and pass without
    checking anything. An instrumented module has undefined `__asan_*` symbols; a normal one none.
    """
    modules = sorted(SANITIZE_VENV.glob("lib/python3*/site-packages/splintercam/_kernels*"))
    nm = shutil.which("nm")
    if not modules or nm is None:
        return False
    undefined = ["-u"] if sys.platform == "darwin" else ["-D", "--undefined-only"]
    listing = subprocess.run(
        [nm, *undefined, str(modules[0])],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return "__asan_" in listing.stdout


def _sanitize_step() -> StepResult:
    if sys.platform == "win32":
        return skip("sanitizer", "no sanitizer build on Windows (MSVC, CMakeLists.txt)")
    env = _sanitizer_env()
    if env is None:
        # A failure, not a skip: a CI job must never pass without having sanitized anything.
        return StepResult(
            "sanitizer", Status.FAIL, 0.0, "no ASan runtime found for this compiler (set CXX?)"
        )

    # A separate environment, so the sanitizer build never contaminates the normal .venv one
    # (UV_PROJECT_ENVIRONMENT), built with SPLINTERCAM_SANITIZE and its own build directory so the
    # two kernel builds do not overwrite each other's compile_commands.json (tools/lint).
    sync_env = dict(os.environ)
    sync_env["UV_PROJECT_ENVIRONMENT"] = str(SANITIZE_VENV)
    sync_argv = [
        "uv",
        "sync",
        "--locked",
        "-C",
        "cmake.define.SPLINTERCAM_SANITIZE=ON",
        "-C",
        f"build-dir={SANITIZE_BUILD_DIR}",
    ]
    code, build_seconds = _run(sync_argv, env=sync_env, label="sanitizer build")
    if code != 0:
        return StepResult(
            "sanitizer", Status.FAIL, build_seconds, f"reproduce: {SANITIZE_REPRODUCE}"
        )

    if not _is_instrumented():
        detail = (
            "the sanitizer environment's kernel module is not instrumented (nm finds no __asan_)"
        )
        return StepResult("sanitizer", Status.FAIL, build_seconds, detail)

    python = SANITIZE_VENV / "bin/python"  # reached only on Linux and macOS (checked above)
    # --capture=sys: a sanitizer report is written to file descriptor 2 and then aborts the
    # process; pytest's default fd capture would swallow it with the process (plan 0004, step 3).
    code, pytest_seconds = _run(
        [str(python), "-m", "pytest", "-q", "--capture=sys"], env=env, label="sanitizer test"
    )
    total = build_seconds + pytest_seconds
    if code != 0:
        return StepResult("sanitizer", Status.FAIL, total, f"reproduce: {SANITIZE_REPRODUCE}")
    return StepResult("sanitizer", Status.PASS, total)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="tools/test", description=__doc__)
    parser.add_argument(
        "--all", action="store_true", help="also run the whole suite against the sanitizer build"
    )
    args = parser.parse_args(argv)
    try:
        build = build_step()
        results: list[StepResult] = [build]
        if build.status is Status.PASS:
            results.append(run_step("pytest", ["pytest", "-q"], reproduce="uv run pytest"))
        else:
            results.append(skip("pytest", "build failed"))
        if args.all:
            results.append(_sanitize_step())
        return finish("test", results)
    except UsageError as error:
        return usage_error("test", error)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
