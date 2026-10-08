# Plan 0006: tools/arch-check

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: `tools/arch-check` enforces the rules of `architecture/modules.yaml` on every Python import and every kernel include under `src/splintercam/`, and `tools/check` runs it instead of reporting it as skipped.
- Specs: none; a tool, specified by `docs/dev/03-architecture-rules.md`, `architecture/modules.yaml` and `tools/README.md`
- Research: none
- Branch: `feat/arch-check`, one pull request
- Owner: Peter Burgener; agents: Claude Code local sessions
- Status (2026-10-08): complete. Steps 1 and 2 done and reviewed, merged in pull request 44 with the label `large-change`.

## Context

- `architecture/modules.yaml` lists seven rules. Peter settled the three dependency rules on 2026-10-08 (PR 42): a module imports only lower layers, or same-layer modules named in its `depends_on`; all `depends_on` together form no cycle; no strategy imports another strategy. The other four are kernels-private, kernel-libraries-only, external-allowlist and apps-use-job-only.
- Python code reaches its kernel as an attribute (`from splintercam import _kernels`, then `_kernels.geometry2d.…`), not by an import, so a plain import checker would miss rule 3.
- Only `foundation` and `geometry2d` have code; `offset2d` is the first module whose kernel will include another module's headers (plan 0005).

## Steps

<!-- Each step has a size estimate (kept code and tests). At 50 % over it, stop and ask, as for a timebox
     (docs/dev/12, section 3). -->

- [x] 1. **The module map and the Python rules.** A reader for the subset of YAML that `modules.yaml` uses (block mappings and lists, inline mappings and lists, comments, quoted and plain scalars), failing on anything else. Checks on the map itself: every `depends_on` entry is a declared module (or the `strategies/*` pattern) of the same or a lower layer, no cycle, no strategy depending on a strategy, apps depending only on `job`, every rule named under `rules` is one the tool checks. Checks on every `.py` under `src/splintercam/`: the file belongs to a declared module; each `splintercam.<module>` import is the module itself or listed in its `depends_on`; `_kernels.<name>` only in module `<name>`; each external package is listed under `external` and allowed in the module. Wrapper `tools/arch-check` (standard library only, like `tools/size-check`), a step in `tools/check`. Tests in `tests/tools/` on small trees in a temporary folder. Size: about 220 lines of kept code + 220 of tests.
- [x] 2. **The kernel rules.** C++ files only in the `kernel/` folder of a module declared with `kernel: true`. Each `#include "…"` resolves inside the module's own kernel, or to a header that another module lists under `kernel_interface`, when that module is in the includer's `kernel_includes`. Each `#include <…>` is a C or C++20 standard header or a header of a library under `kernel_libraries` whose `used_by` names the module; nanobind only in `bindings.cpp`. Vendored code in `kernel/vendor/` is not scanned (ADR 0009). The `kernel_interface` key on geometry2d's entry in `architecture/modules.yaml` (Peter, 2026-10-08). `tools/README.md`, `docs/dev/03` and `docs/dev/06` say "script" instead of import-linter. Size: about 120 lines of kept code + 120 of tests.

## Decisions

- 2026-10-08: standard library, no import-linter and no YAML package, because import-linter cannot express "same layer only when named", the kernel attribute, includes or external packages, so a script was needed anyway; no ADR, and the tool runs without `tools/bootstrap` (Peter).
- 2026-10-08: `depends_on` is the full list of what a module may import, lower layers included: an import of a lower-layer module that its entry does not name fails, so the entries stay true (Peter).
- 2026-10-08: the headers a module offers to other kernels are listed in `modules.yaml` as `kernel_interface` on the providing module's entry; its SPEC keeps the prose (Peter).
- 2026-10-08: both steps in one pull request if together they stay under 400 added lines of non-test code; otherwise step 2 waits for the next session.
- 2026-10-08: they came to 644 added lines (estimate 340, +89 %); one pull request with the label `large-change` all the same, since the reader and the two rule sets share the map and a split would still need the label (Peter).

## Progress log

<!-- Newest first. What was done, what tools/check reported, what is next. At most about 30 lines per session;
     numbers go into tables. Above 300 lines, older entries move to an archive file next to the plan. -->

### 2026-10-08, closed

- Peter reviewed and merged pull request 44. The plan moved to `docs/plans/completed/`; the Backlog stays open for later plans.

### 2026-10-08, session 1

- Drafted from Peter's three answers above.
- Done, steps 1 and 2: `tools/arch-check` (`tools/lib/module_map.py`, `arch_python.py`, `arch_kernels.py`, `cmd_arch_check.py`, `standard-headers.txt`), a step of `tools/check`; `kernel_interface: [exact.hpp, distance.hpp, grid.hpp]` on geometry2d's entry and the rule comments in `architecture/modules.yaml` (Peter's answer, applied); `tools/README.md`, `AGENTS.md`, `docs/dev/03` and `06` updated. The repository passes every rule.
- Tests: 31 in `tests/tools/test_arch_check.py` and `test_module_map.py`, 81 in `tests/tools/` in all. Written after the code, so each rule check was mutated by hand: every mutation failed a test.
- Reviews: simplifier (graphlib for the cycle; quoted includes resolve only next to the file, since no include directory points into `src/`; dead guards removed); test-auditor (no test weakened; tests added for six checks no test reached; duplicate keys refused; every C and C++ suffix placed).
- `tools/check`: PASS (12 of 14; trace-check and licence-check not written yet).
- Size: 644 lines of non-test code added (`module_map.py` 226, `arch_python.py` 167, `arch_kernels.py` 120, `cmd_arch_check.py` 88), 425 of tests.
- Next: Peter's review of the pull request. Then the plan moves to `docs/plans/completed/`.

## Backlog

<!-- Nice-to-have review findings: recorded here, not coded in the change that found them. -->

- Public interfaces (`docs/dev/03`, Public interfaces): an import of another module's underscore name or submodule is not checked; no rule in `modules.yaml` names it yet.
- `tools/lib/modules.py` still reads names and budgets with patterns. Switching it to `module_map.py` would remove that copy, but the reader requires `kernel` on every entry and `tests/tools/test_size_check.py` feeds a map without it, so the test would have to change.
- PySide6's `banned_submodules` stay with `tools/licence-check` (`tools/README.md`).
- Not seen by the check (test-auditor): imports in `src/splintercam/__init__.py`; a kernel reached through `getattr` or `importlib`; `#include MACRO`; a duplicate key inside an inline mapping; a list item `- key: value` read as a string.
- `src/splintercam/foundation/SPEC.md`, REQ-FND-005 and 008, say "architecture check pending (`tools/arch-check`)": no global state and no literal tolerances are rules `modules.yaml` does not list, so arch-check does not check them.

## Blockers

- None.
