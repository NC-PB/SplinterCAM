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

- [ ] 1. **Bootstrap.** Run `tools/bootstrap` and `tools/check` (install uv and git-lfs first if your environment lacks them). While there are no kernels, the first build replaces the committed stub `src/splintercam/_kernels/__init__.pyi` by `src/splintercam/_kernels.pyi`: commit that. Get CI green on the three systems (`check.yml`); if `sanitize.yml` fails only because there are no kernels, report it and do not edit workflows. Fix links in `docs/dev/`, `docs/glossary.md`, `docs/templates/`, `AGENTS.md` and `tools/README.md` that point to files not in this repository: decisions and sources point to `docs/spike/`; other Project Spike files (its DECISIONS, QUESTIONS, ROADMAP, CHANGES, other research topics) are named as plain text "(Project Spike)" without a link. Mentions of `test_repo` in `docs/dev/` mean this repository's own files now. List broken links you find in the protected folders in the progress log instead of fixing them. Size: no kernel code; docs only.
- [ ] 2. **foundation: the tolerance budget.** Bring `src/splintercam/foundation/SPEC.md` to the proposed rows of `docs/spike/foundation-SPEC-draft.md`: the changes to REQ-FND-001 and 002 and the new REQ-FND-008 and 009 (D-056, D-146, D-149; research 01, section Tolerances, tests 14 and 15). Mark them `Reviewed` (they come from decisions Peter accepted). Tests first, tagged with the REQ IDs, including the numbers of research 01 tests 14 and 15 and a property test that the four parts sum to tol and that tol below tol_min = 2/875 mm is refused with `TOL_BELOW_MINIMUM` naming 0.0022858 mm. Then the code; defaults in a documented defaults file as REQ-FND-008 says. Size: about 150 lines of kept code + 200 of tests.
- [ ] 3. **Lean-code tools** (`docs/dev/12-lean-code.md`, section 8). Write `tools/size-check` with the file, function and module limits of section 3 and add it to `tools/check`; the `simplifier` agent is already in `.claude/agents/`. The ruff and clang-tidy limits live in `pyproject.toml` and `.clang-tidy`, which are protected: write the proposed changes as `docs/plans/active/0001-protected-changes.patch` and list them for Peter; do not apply them. Size: about 150 + 80.
- [ ] 4. **geometry2d: SPEC draft for the topic 01 part** (no code). Write `src/splintercam/geometry2d/SPEC.md` from `docs/research/01-foundations.md` with `docs/templates/SPEC.md`, in the EARS style of the foundation SPEC. Cover the sections Vectors and exact signs, Curves (arc form and validation), Distances, Circle through three points, Flattening with a known error side, Area and orientation, Point in region, Loop tree, Kernel arrays, Helpers, Interfaces and Degenerate input; say where Frames and transforms belong if not here. One requirement per testable statement, each citing its research section and the research test it is checked by; status `Draft`. Mark which requirements need Clipper2 (the loop tree's PolyTree and its fallback difference) and which part goes into the C++ kernel under the split rule of `docs/dev/03`. Then **stop**: Peter reviews the draft before any geometry2d code.

## Decisions

- 2026-10-02: one pull request per step; steps 1 to 3 run without waiting for review unless a "Stop and ask" condition of `AGENTS.md` applies; step 4 ends the plan, because a SPEC needs Peter's review before code (D-156).

## Progress log

<!-- Newest first. What was done, what tools/check reported, what is next. At most about 30 lines per session. -->

### 2026-10-02, session 1, step 1 (bootstrap)

- Plan: run `tools/bootstrap` and `tools/check` on Linux (uv and git-lfs are installed here). Commit the stub `src/splintercam/_kernels.pyi` that the first build writes in place of `src/splintercam/_kernels/__init__.pyi`. Scan every relative link in the Markdown files; fix those in `docs/dev/`, `docs/glossary.md`, `docs/templates/`, `AGENTS.md` and `tools/README.md` (ADRs to `docs/adr/`, decisions and sources to `docs/spike/`, other Project Spike files as plain text "(Project Spike)", `test_repo` paths to this repository's files); list the broken links of the protected `docs/adr/`, `docs/research/` and `docs/spike/` here. Open the pull request, get `check.yml` green on Linux, macOS and Windows, and report `sanitize.yml`.

## Backlog

## Blockers
