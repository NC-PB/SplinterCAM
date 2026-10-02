# Plan 0001: Bootstrap and foundation

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: SplinterCAM checks green on Windows, macOS and Linux; `foundation` meets its SPEC including the tolerance budget of D-146 and D-149; the lean-code tools exist; the topic 01 part of `geometry2d` has a SPEC draft waiting for Peter's review.
- Specs: `src/splintercam/foundation/SPEC.md`; the proposed rows in `docs/spike/foundation-SPEC-draft.md`; new `src/splintercam/geometry2d/SPEC.md` (step 4, draft only)
- Research: `docs/research/01-foundations.md` (readiness L4)
- Branch: one branch and one pull request per step
- Owner: Peter Burgener; agents: Claude Code cloud sessions

## Context

- Early start under D-156 (2026-10-02): this repository starts before the research phase hands over. Decisions and sources stay registered in Project Spike; `docs/spike/` holds snapshots. Never edit `docs/spike/`, `docs/adr/` or `docs/research/`.
- The seed was assembled on 2026-10-02 from the stack test app (scaffold, `foundation` code and tests, agent files) and from Project Spike (development docs, ADRs, glossary, research 01, templates), renamed from `opencam` to `splintercam`. `tools/check` passed on Linux before the first commit.
- Only Python and NumPy are needed for steps 1 to 3. The kernel build machinery (CMake, nanobind, Clipper2) stays; there are no kernels yet.

## Steps

- [x] 1. **Bootstrap.** Run `tools/bootstrap` and `tools/check` (install uv and git-lfs first if your environment lacks them). While there are no kernels, the first build replaces the committed stub `src/splintercam/_kernels/__init__.pyi` by `src/splintercam/_kernels.pyi`: commit that. Get CI green on the three systems (`check.yml`); if `sanitize.yml` fails only because there are no kernels, report it and do not edit workflows. Fix links in `docs/dev/`, `docs/glossary.md`, `docs/templates/`, `AGENTS.md` and `tools/README.md` that point to files not in this repository: decisions and sources point to `docs/spike/`; other Project Spike files (its DECISIONS, QUESTIONS, ROADMAP, CHANGES, other research topics) are named as plain text "(Project Spike)" without a link. Mentions of `test_repo` in `docs/dev/` mean this repository's own files now. List broken links you find in the protected folders in the progress log instead of fixing them. Size: no kernel code; docs only.
- [x] 2. **foundation: the tolerance budget.** Bring `src/splintercam/foundation/SPEC.md` to the proposed rows of `docs/spike/foundation-SPEC-draft.md`: the changes to REQ-FND-001 and 002 and the new REQ-FND-008 and 009 (D-056, D-146, D-149; research 01, section Tolerances, tests 14 and 15). Mark them `Reviewed` (they come from decisions Peter accepted). Tests first, tagged with the REQ IDs, including the numbers of research 01 tests 14 and 15 and a property test that the four parts sum to tol and that tol below tol_min = 2/875 mm is refused with `TOL_BELOW_MINIMUM` naming 0.0022858 mm. Then the code; defaults in a documented defaults file as REQ-FND-008 says. Size: about 150 lines of kept code + 200 of tests.
- [ ] 3. **Lean-code tools** (`docs/dev/12-lean-code.md`, section 8). Write `tools/size-check` with the file, function and module limits of section 3 and add it to `tools/check`; the `simplifier` agent is already in `.claude/agents/`. The ruff and clang-tidy limits live in `pyproject.toml` and `.clang-tidy`, which are protected: write the proposed changes as `docs/plans/active/0001-protected-changes.patch` and list them for Peter; do not apply them. Size: about 150 + 80.
- [ ] 4. **geometry2d: SPEC draft for the topic 01 part** (no code). Write `src/splintercam/geometry2d/SPEC.md` from `docs/research/01-foundations.md` with `docs/templates/SPEC.md`, in the EARS style of the foundation SPEC. Cover the sections Vectors and exact signs, Curves (arc form and validation), Distances, Circle through three points, Flattening with a known error side, Area and orientation, Point in region, Loop tree, Kernel arrays, Helpers, Interfaces and Degenerate input; say where Frames and transforms belong if not here. One requirement per testable statement, each citing its research section and the research test it is checked by; status `Draft`. Mark which requirements need Clipper2 (the loop tree's PolyTree and its fallback difference) and which part goes into the C++ kernel under the split rule of `docs/dev/03`. Then **stop**: Peter reviews the draft before any geometry2d code.

## Decisions

- 2026-10-02: one pull request per step; steps 1 to 3 run without waiting for review unless a "Stop and ask" condition of `AGENTS.md` applies; step 4 ends the plan, because a SPEC needs Peter's review before code (D-156).

## Progress log

<!-- Newest first. What was done, what tools/check reported, what is next. At most about 30 lines per session. -->

### 2026-10-02, session 1, step 2 (tolerance budget)

- Plan: take the changed REQ-FND-001 and 002 and the new 008 and 009 from `docs/spike/foundation-SPEC-draft.md` into the SPEC, marked `Reviewed`, with the draft's interface (`BUDGET_PARTS`, `stage_shares` as (part, share) pairs). Where the draft leaves the design open, choose and flag it for Peter: the shares stay the base shares of REQ-FND-008; `stage_tol_mm` gives each part as REQ-FND-009 computes it (geometry plus the grid cost, fit minus it, clamped at 0); `ToleranceSet.for_operation(tol_mm)` returns a `Result` and takes no `Context`, which holds the set; t_flat and t_topo are properties; the defaults live in `src/splintercam/foundation/tolerance_defaults.toml` (read with the standard library's `tomllib`), exposed as `TOLERANCE_DEFAULTS`. Tests first: research 01 tests 14 and 15, and property tests for the sum of the parts and the refusal below tol_min, written by the `test-designer` agent from the SPEC and research only; the existing tests are moved to the four parts. Then the code, `tools/check`, the reviews (`simplifier`, `test-auditor`, `spec-reviewer`) and the pull request, stacked on step 1's.
- Done: SPEC rows REQ-FND-001, 002 (changed), 008, 009 (new), all `Reviewed`; the header's two broken links fixed. Tests first (two `test-designer` agents, from the SPEC and research only; each checked its tests against a throwaway reference): they failed on the missing names, then passed against the code on the first run. Code: `ToleranceSet` with (part, share) pairs, `stage_tol_mm` per REQ-FND-009, `for_operation`, `flatten_tol_mm`, `topology_tol_mm`; `tolerance_defaults.toml` with 16 declared parameters, read into `TOLERANCE_DEFAULTS`; the custom `__hash__` and `__reduce__` are gone. Research 01 tests 14 and 15 hold as written: tol_min is the double nearest 2/875, the fit band there clamps from −6.8e-20 mm to 0, and the refusal names 0.0022858 mm. The wheel ships the TOML file.
- `tools/check`: PASS (8 of 13 steps, the same skips as step 1); `tools/test-one foundation`: 121 passed. The property tests also pass with 10 000 cases each (`HYPOTHESIS_PROFILE=thorough`, test-auditor).
- Reviews: `simplifier` (no must-fix; about 29 lines of nice-to-have), `test-auditor` (asked to restore the tests of geometry, fit and t_flat for non-default shares, which trimming had removed: restored), `spec-reviewer` (no must-fix, the arithmetic checked by hand; four spec gaps, now open questions in the SPEC). Each finding was checked by a second agent.
- Size: `src/` +212 −60 (kept code +152, on the estimate of 150), tests +598 −148 (+450 against about 200: over the 50 % margin of `docs/dev/12`, section 3), SPEC, module AGENTS.md and glossary +87 −27. The tests that remain are the plan's explicit asks (tests 14 and 15, the sum and refusal properties), the per-part formulas, and REQ-FND-002's new missing, unknown and repeated parts; duplicates were removed.
- Questions for Peter: the design choices and the spec gaps listed under the SPEC's open questions (shares as base shares with the grid cost in `stage_tol_mm`, `for_operation` without a `Context`, TOML read with `tomllib` in a module that had no I/O, the constructor below tol_min, the NCX clause of REQ-FND-009, the range of tol in the defaults file); and whether the test size is acceptable or the estimate was meant for new tests only.
- Next: step 3.

### 2026-10-02, session 1, step 1 (bootstrap)

- Plan: run `tools/bootstrap` and `tools/check` on Linux (uv and git-lfs are installed here). Commit the stub `src/splintercam/_kernels.pyi` that the first build writes in place of `src/splintercam/_kernels/__init__.pyi`. Scan every relative link in the Markdown files; fix those in `docs/dev/`, `docs/glossary.md`, `docs/templates/`, `AGENTS.md` and `tools/README.md` (ADRs to `docs/adr/`, decisions and sources to `docs/spike/`, other Project Spike files as plain text "(Project Spike)", `test_repo` paths to this repository's files); list the broken links of the protected `docs/adr/`, `docs/research/` and `docs/spike/` here. Open the pull request, get `check.yml` green on Linux, macOS and Windows, and report `sanitize.yml`.
- Done: `tools/bootstrap` (PASS, 24 s cold) and `tools/check` on Linux. The first build replaced `src/splintercam/_kernels/__init__.pyi` by `src/splintercam/_kernels.pyi`, committed. Beyond "docs only": `tools/build` stamped the SPDX header only on stubs inside `_kernels/`, so the single file had none (AGENTS.md: every file starts with it); `tools/lib/cmd_build.py` now stamps both and removes a stale single-file stub before regenerating. `tools/test --all` passes on Linux, sanitizer included: nanobind's own code is instrumented, so the canary finds `__asan_` symbols without kernels.
- Links: the 69 broken links in `docs/dev/`, `docs/templates/` and `tools/README.md` are fixed (none in `docs/glossary.md` or `AGENTS.md`), and the plain-text `engineering/12` and `docs/research/18` and `24` in the templates. `docs/dev/12` keeps `test_repo` once on purpose: SRC-118 is a commit of the test app's repository. The two broken links in `src/splintercam/foundation/SPEC.md` wait for step 2, which rewrites it.
- Broken links in protected folders, not fixed (36):

| File | Targets not in this repository |
| --- | --- |
| `docs/adr/0002` | `../research/05-…`, `../engineering/09-…` |
| `docs/adr/0003` | `../engineering/08-…` |
| `docs/adr/0004` | `../plans/0001-stack-test-app.md`; `../engineering/` 02, 03, 04, 06, 09 (3×), 10 |
| `docs/adr/0005`, `0008` | `../research/18-known-pitfalls.md#general-engineering` (2×), `../research/11-…` |
| `docs/adr/README.md` | `../DECISIONS.md`, `../engineering/05-…#decision-records`, `../plans/0001-stack-test-app.md` |
| `docs/research/01-foundations.md` | `README.md` (2×), `02-…` (3×), `11-…`, `21-…`, `25-…`, `../engineering/03-…` (2×), `../decisions/0004-…`, `../reviews/2026-09-27-readiness-audit.md#01-foundations`, `../AGENTS.md#readiness-levels`, `../ASSUMPTIONS.md` (A-001, A-043) |
| `docs/spike/2026-10-01-delta-plan-0001.md` | `../reviews/2026-10-01-prototype-insights.md`, `foundation-SPEC.md` (here `foundation-SPEC-draft.md`), `geometry2d-SPEC.md` |

- `tools/check`: PASS (8 of 13 steps; skipped: clang-format and clang-tidy, no C++ files; arch-check, trace-check and licence-check, not written yet).
- CI on [pull request 1](https://github.com/NC-PB/SplinterCAM/pull/1), commit 9f0d2ac: `check.yml` green on ubuntu-24.04 (48 s), macos-15 (60 s) and windows-2025 (174 s); `sanitize.yml` green (54 s), so no kernels are needed for it.
- Reviews: a link verifier, a build reviewer and `test-auditor` (PASS, no test touched); their two must-fix findings are in.
- Size: `src/` +6 −7 (the stub), `tools/` +11 −5, docs +63 −63 (links), tests 0.
- Questions for Peter: (1) D-156 is cited by `AGENTS.md`, this plan and `docs/dev/README.md` but has no row in `docs/spike/decisions-snapshot.md`; neither has D-135, cited by the sources snapshot. (2) `docs/dev/README.md` said "Change the concept here [Project Spike], not there"; step 1 edited this copy, as the plan asks. Which copy of `docs/dev/` is the master now?
- Next: step 2.

## Backlog

- Step 2 review, nice-to-have: inline `_read_defaults` (one caller); one shared test helper for the D-056 shares, eps values and the refusal assertion, used now in three test files; the unit and property tests both pin 0.0022857 and the double below tol_min; the order check in `test_tolerance_set.py` is implied by the equality test; the reader could reject booleans and quoted numbers; an import-time check that the floor term applies at tol_min (true for the declared values); the duplicated-part test could again draw any part at any position.
- `_context.py`'s docstring names `src/splintercam/geometry2d/kernel/offset.cpp`, which is not in this repository.

- "plan 0001" in `docs/dev/12` (its first section and section 8) and `docs/dev/03` means the stack test app's plan; read as this repository's plan, section 8 would exempt it from the lean-code limits. Name it as `docs/dev/07` and `10` now do (step 1 review).
- `.claude/agents/test-designer.md` and `.claude/skills/implement-requirement/SKILL.md` point to `docs/research/18` and `24`, which are in Project Spike only (agent files, outside step 1's list).
- A test that every committed kernel stub starts with the SPDX line, unless `tools/licence-check` covers `.pyi` files (step 1 review).
- Before the first kernel: `from splintercam._kernels import geometry2d` gives pyright's `reportMissingModuleSource` warning, which `tools/lint` treats as an error; `import splintercam._kernels as kernels` with attribute access does not. Choose the import pattern, or a pyright setting in `pyproject.toml` for Peter (step 1 review).

## Blockers
