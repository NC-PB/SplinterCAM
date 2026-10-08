# AGENTS.md

<!-- Map for AI coding agents. Keep under 150 lines. Link to docs/, do not copy them.
     Add a Gotcha when an agent makes the same mistake twice. Placeholders are in <angle brackets>. -->

SplinterCAM is an open-source CAM system for CNC milling and turning, licensed Apache-2.0.
Status: early start of release 1 (D-156): `foundation` done; `geometry2d` slices 1 and 2 (topic 01: exact predicates, lines and arcs, flattening, area, point in region, cleanup; the loop tree, the machining region and open chains) done and reviewed; `offset2d` drafted (plan 0005, waiting for research 02). The stack test app runs in a separate repository. Stack: a Python application (PySide6 GUI, OCCT through OCP) with C++20 compute kernels built with nanobind (docs/adr/0004-tech-stack.md).

## Start here

- Current work: none. Work continues in local sessions. Next: `docs/plans/active/0005-offset2d.md`, a draft that waits for research 02 and Peter's two questions. Records of the finished slices: `docs/plans/completed/0003-geometry2d-slice-1.md` and `docs/plans/completed/0004-geometry2d-slice-2.md` (Handover).
- Work one plan step at a time. At the end of each step, tick it, write a progress-log entry in the plan, run `tools/check`, and commit. One pull request per session, with small code changes included; a new algorithm or a change over about 100 lines of non-test code gets its own (docs/dev/07, Branches, commits and pull requests). The plan says where to stop for the user's review.
- Decisions (D-nnn) and sources (SRC-nnn) are registered in Project Spike until the handover; `docs/spike/` holds dated snapshots. Never edit them. If a decision seems wrong or missing, stop and write the question in the progress log.

## Where to look

| You need | Read |
| --- | --- |
| What a module must do | `src/splintercam/<name>/SPEC.md` (requirements `REQ-…`, invariants) |
| A module's C++ part | `src/splintercam/<name>/kernel/` |
| The maths behind it | the `docs/research/` section the SPEC cites (read only that one) |
| What you may import | `architecture/modules.yaml` |
| Another module's interface | `docs/generated/api/<module>.md` (not its source) |
| Work in progress | `docs/plans/active/` |
| Why a module is built as it is, and what was rejected | `src/splintercam/<name>/DECISIONS.md` |
| Why things are as they are across modules | `docs/adr/`, and the decisions in `docs/spike/decisions-snapshot.md` |
| The right name for a domain term | `docs/glossary.md` |
| Code, test and workflow rules in full | `docs/dev/` |

## Commands

Run from the repository root. All are stack-neutral wrappers in `tools/`.

- `tools/check`: format, lint, size, build, tests of changed modules, architecture, traceability and licence checks. Must pass before you report a task as done.
- `tools/size-check`: the file, function and module size limits of `docs/dev/12`, section 3.
- `tools/test-one <module> [filter]`: fast loop for one module.
- `tools/test`: the full suite.
- `tools/render <case>`: SVG/PNG of a test case's input, debug geometry and output. Look at it after any geometry change.
- `tools/replay <failure-file>`: re-run a dumped failing input.
- `tools/golden-diff <case>`: how the output differs from the approved golden files.
- `tools/new-module <name>`: scaffold a module (only when asked).
After cloning, run `tools/bootstrap`; on Windows, run the `tools/` scripts from Git Bash. Written so far: `bootstrap`, `build`, `format`, `lint`, `test-one`, `test`, `size-check`, `check` (`tools/README.md` says what each wraps). `tools/check` reports the checks that do not exist yet as skipped. `render`, `replay`, `golden-diff` and `new-module` come in later plan steps.

## How to work

1. Find the requirement IDs for your task in the module's `SPEC.md`. If there are none, draft them and ask for approval before coding. Implement only requirements marked `Reviewed`, or those the active plan releases explicitly.
2. Read that `SPEC.md`, the module's `AGENTS.md` and `DECISIONS.md`, and the one research section it cites. Check `docs/plans/active/` for a plan.
3. Write or extend the tests first, tagged with the requirement ID. Run `tools/test-one` and see them fail for the expected reason.
4. Implement in small steps. Run `tools/test-one` after each step.
5. Run `tools/check`. For geometry or toolpath changes run `tools/render` on the affected cases and look at the images.
6. Update the SPEC's "Verified by" column, the plan's progress log, and the glossary if you introduced a term. Decisions and pitfalls are already recorded (see Keep the record).
7. Report: files changed, tests added, commands run with their results, open questions. Name every file by its path from the repository root, for example `src/splintercam/geometry2d/SPEC.md`.

## Keep the record

Record as you go, in the same commit as the change, without being asked (docs/dev/05, "Keep the record as you go"):

- A choice between alternatives, or an answer from Peter: an entry in the module's `DECISIONS.md` with why and what was rejected.
- Something that cost time or could trip the next agent: one line in the module's `AGENTS.md`, Known pitfalls.
- Before changing or removing existing behaviour: find why it is there (`DECISIONS.md`, SPEC, `git log -L`), name it in the pull request, and ask if you find no reason or the decision is Peter's.

## Rules

- Units inside the code: millimetres and radians. Degrees only in UI, human-readable files and G-code.
- Tolerances come from the `ToleranceSet` in the `Context`. Never write a literal epsilon or a magic number.
- Respect `architecture/modules.yaml`: no imports from higher layers, no strategy imports another strategy.
- Split rule: loops over points, segments, triangles or cells go into the module's C++ `kernel/` or vectorised NumPy, never into a Python loop. Loops over operations, tools, features, files and UI stay in Python.
- Kernels take and return NumPy arrays and plain values. No OCCT, Qt or Python headers in kernel code; only `bindings.cpp` includes nanobind.
- OCCT only through OCP, and only in `io`, `features` and `apps/desktop`; between modules a shape is a `ShapeRef`, never an OCCT object. PySide6 only in `apps/desktop`.
- Python: type hints everywhere, pyright strict clean. C++: no `new` or `delete`, warnings are errors, the sanitizer build stays clean.
- Output is deterministic: stable sorts with tie-breakers, no hash-order output, seeded randomness, fixed merge order.
- Expected outcomes (empty region, tool does not fit) are returned as typed diagnostics. Never swallow errors.
- Cite the source of every algorithm and constant in a comment: research section, paper or tool maker.
- Public interface changes need a SPEC change. New dependencies need an ADR (draft it, a person decides).
- Every file starts with `SPDX-License-Identifier: Apache-2.0`.
- Keep files under 400 lines and functions under 60 where you can; follow the nearest existing module's patterns.

## Never

- Never weaken, skip or delete a test, remove an assertion or loosen a tolerance to make a check pass. If a test looks wrong, stop and explain.
- Never edit `testdata/golden/`. Use `tools/golden-diff`; a person approves.
- Never copy code from other CAM software, GPL or LGPL projects, Stack Overflow, or sources without a licence. Permissive code only with attribution in `NOTICE`.
- Never read, search or describe proprietary CAM source code.
- Never read, list or search files outside this repository. The folders around it hold unrelated and proprietary material.
- Never change `LICENSE`, `NOTICE`, accepted ADRs, CI configuration or agent settings unless asked.
- Never guess machine or controller behaviour (G-code dialects, canned cycles, kinematics, safe heights). Ask, or cite a manual.

## Done means

- `tools/check` passes, with no new warnings.
- New behaviour has tests tagged with requirement IDs; no test was weakened.
- SPEC, plan and glossary are updated; every decision of the change is in the module's `DECISIONS.md`.
- The change is reviewable: about 400 lines of non-test code at most, one module.

## Questions

Sort every question before asking (docs/dev/07, "Questions: who answers"):

1. **Peter's judgement** (scope, what the user sees, machine and controller behaviour, safety, licences, dependencies, `modules.yaml`, interfaces between modules, accepted decisions): ask Peter in machining terms, what happens on the machine under each option, with your recommendation.
2. **Technical inside the module** (algorithms, numerics, edge cases, deviations from research backed by a test, a measurement or a source): decide it yourself as "(ours)", record it in `DECISIONS.md` with the evidence, list it in the pull request under "Deviations and decisions". Do not ask Peter.
3. **Knowledge nobody has at hand:** write a research request in `docs/research/REQUESTS.md`. Do not ask Peter.

Never block: take the conservative option, record it as provisional, continue. Stop at once only when a test looks wrong, a tolerance would have to be loosened, the same approach failed three times, or no requirement covers what the code needs.

Every file you name, anywhere, is its path from the repository root in backticks: `src/splintercam/geometry2d/SPEC.md`, never "the SPEC".

## Gotchas

<!-- One or two lines each. Examples from the research; replace with real ones as they happen. -->
- A flattened arc lies inside the true arc; on convex walls that is a gouge, not just roughness (docs/research/01).
