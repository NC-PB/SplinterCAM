# tools/: the command contract

Agents and people run the same commands, whatever the stack. Each command is a small executable script in `tools/` that calls the real build system. Changing the build system later then changes these scripts, not the agent instructions. Implement them after [ADR 0004](../docs/adr/0004-tech-stack.md).

## Commands

| Command | Does | Time budget |
| --- | --- | --- |
| `tools/bootstrap` | Install or check the toolchain and restore dependencies | once |
| `tools/build [module]` | Build everything or one module | under 1 min incremental |
| `tools/format [file…]` | Format files (all changed files without arguments) | seconds |
| `tools/lint [module]` | Linters and analyzers, warnings as errors | under 1 min |
| `tools/test-one <module> [filter]` | Unit and property tests of one module | under 30 s |
| `tools/test [--all]` | Tests of changed modules and their dependents; `--all` for everything | minutes |
| `tools/check [--fast]` | format check, lint, `size-check`, build, tests of changed modules, `arch-check`, `trace-check`, `licence-check` | under 5 min |
| `tools/size-check [--change BASE [--large-change]]` | File, function and module size limits of [docs/dev/12](../docs/dev/12-lean-code.md), section 3; with `--change`, only the lines of non-test code added against BASE | seconds |
| `tools/arch-check` | Enforce `architecture/modules.yaml` | seconds |
| `tools/trace-check` | Requirements without tests, tests with unknown IDs; writes `docs/generated/traceability.md` | seconds |
| `tools/licence-check` | SPDX headers (REUSE), dependency licences, `testdata/LICENSES.md` entries | seconds |
| `tools/render <case> [--debug]` | SVG/PNG of a test case's input, debug geometry and output into `out/render/<case>/` | seconds |
| `tools/replay <failure-file> [--minimise]` | Re-run a dumped failing input; optionally shrink it | varies |
| `tools/golden-diff <case>` | Compare current output with the approved golden files; numbers and a render | seconds |
| `tools/golden-approve <case>` | Copy current output to `testdata/golden/` (people only; denied to agents) | seconds |
| `tools/docs` | Regenerate `docs/generated/` (API summaries, module graph) | seconds |
| `tools/new-module <name>` | Scaffold a module from the templates | seconds |
| `tools/bench [module]` | Benchmarks against the performance budgets | minutes |

## Implementation (ADR 0004)

The scripts were written in the stack test app (its plan 0001, in the test app's own repository). Written so far: `bootstrap`, `build`, `format`, `lint`, `test-one`, `check`, `test` there, and `size-check` (this repository's plan 0001, step 3) and `arch-check` (plan 0006) here.

`build` regenerates the kernel stubs in `src/splintercam/_kernels/` (nanobind stubgen; while no module has a kernel, the single file `src/splintercam/_kernels.pyi`) after every `uv sync`, so pyright sees the kernel API even though the compiled module itself is what Python imports.

Each command is a short bash script (on Windows, run it from Git Bash). `bootstrap` is plain bash; the others check that `tools/bootstrap` has run (`lib/env.sh`) and hand over to typed Python in `lib/cmd_<command>.py`, which `tools/lint` checks like the rest of the code. Every tool (CMake, Ninja, ruff, pyright with its own Node.js, clang-format, clang-tidy) comes from PyPI at the version pinned in `uv.lock`, so all three systems run the same versions.

What each one wraps:

| Command | Wraps |
| --- | --- |
| `bootstrap` | Checks for uv and git-lfs, then `uv sync --locked`: installs the pinned uv-managed Python, the dependencies, and builds the kernels through scikit-build-core |
| `build` | `uv sync --locked`. The project is installed editable and built without isolation into `build/<wheel tag>/`; uv rebuilds it when a file listed under `[tool.uv] cache-keys` in `pyproject.toml` changes, and CMake recompiles only what changed |
| `format` | `ruff format` and `ruff check --select I --fix` (import order), `clang-format`; `--check` checks every file |
| `lint` | `ruff check`, `pyright --warnings` (strict), `clang-tidy --verify-config`, `clang-tidy` on the kernel sources with the build's `compile_commands.json` (on macOS with the SDK from `xcrun`; skipped on Windows, where the Visual Studio generator writes no compile database) |
| `test-one` | `pytest tests/<module>` with Hypothesis, after `build`; requirement IDs work as `-k` keywords (`REQ_OFF_003`) |
| `test` | `build`, then `pytest` over the whole suite. `--all` additionally builds the kernels a second time with `SPLINTERCAM_SANITIZE` (CMakeLists.txt) into a separate `.venv-sanitize` environment and reruns the suite against it with the ASan/UBSan runtime preloaded (Linux and macOS only; skipped on Windows, which has no supported sanitizer build) |
| `check` | `build`, `format --check`, `lint`, `size-check`, `arch-check`, `pytest`. First version: runs the whole suite, and reports `trace-check` and `licence-check` as skipped until they exist |
| `size-check` | A script: files over 400 lines reported and over 800 failing (generated files excepted), Python functions over 60 lines reported, each module's NLOC against the `budget` in `modules.yaml` (over it reported, over it + 20 % failing); a file it cannot parse fails. The hard function limits are ruff's and clang-tidy's, in `lint` (`docs/plans/completed/0001-protected-changes.patch`, applied). NLOC leaves out comments and docstrings, as lizard does. With `--change BASE`, only the change limit: lines of non-test code added since the merge base, over 200 reported, over 400 failing unless `--large-change`; tests, test data, Markdown and generated files and removed lines do not count, binary files are named (plan 0002). Needs only the standard library, so it runs without `bootstrap` |
| `arch-check` | A script on the standard library (Peter, 2026-10-08, plan 0006): reads `modules.yaml` in full (`lib/module_map.py`, the YAML subset it uses) and checks the map itself (declared dependencies, layers, cycles, the rule list), every Python import under `src/splintercam/` (`lib/arch_python.py`, including `_kernels.<module>`) and every kernel include (`lib/arch_kernels.py`: standard headers, `kernel_libraries`, `kernel_interface`). One line per violation, `path:line: rule: what`. Runs without `bootstrap`, like `size-check` |
| `trace-check` | A script reading the `@pytest.mark.req` markers and the requirement tables in the SPEC files |
| `licence-check` | `reuse lint`, a licence report of the lock file (LGPL accepted only in the `test-oracle` group, ADR 0010), the banned Qt modules, `testdata/LICENSES.md` |
| `render` | A script drawing the debug-sink output as SVG; screenshots of the viewer for 3D cases |
| `docs` | Generates API summaries from `__all__` and docstrings, and the module graph from `modules.yaml` |

## Conventions for every command

- Run from the repository root; no arguments needed for the common case.
- Exit code 0 = success, 1 = check failed, 2 = wrong usage or missing tool.
- Last line of output is a one-line summary (`check: FAIL (2 lint errors, 1 test)`), so an agent can read the result without scrolling.
- `--json` prints a machine-readable result where it makes sense (`test`, `check`, `trace-check`, `golden-diff`).
- Failures print the exact command to reproduce them (`tools/test-one geometry2d REQ_OFF_003`).
- Nothing writes outside the repository except caches of the build system; outputs go to `out/` (ignored by git).
- Works the same on a developer machine and in CI.

## Hooks for Claude Code

`hooks/guard-protected-paths` and `hooks/format-changed-file` are called by `.claude/settings.json`. They read the hook input as JSON on stdin and need only bash, sed and grep. `hooks/protected-paths.txt` lists the protected paths; accepted ADRs are detected by their status line.
