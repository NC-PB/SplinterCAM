[Index](README.md) · [← 11. User interface](11-user-interface.md)

# 12. Lean code

> **Status: accepted** 2026-10-01 (CP-006, D-139). Written from what plan 0001 of the stack test app showed. The limits are declared tool settings; changing them needs a decision.

Agents write code quickly and delete it rarely. Without limits that are checked, a code base grows faster than anyone can review it, and every extra line is one more place for a CAM error to hide. This document says what counts as bloat, which limits apply, which tools check them, and how reviews and throwaway code are handled so the code stays small.

## What plan 0001 of the stack test app showed

From the prototype at commit c1c21d3 (SRC-118 in the [sources snapshot](../spike/sources-snapshot.md); review `reviews/2026-10-01-prototype-insights.md` (Project Spike)):

- **Where a SPEC bounded the work, the code stayed lean.** `foundation` and the `geometry2d` offset: 980 lines in `src/`, 12 Python functions, one longer than 50 lines. Requirements, tests written from the SPEC and reviews kept it small.
- **Where nothing bounded it, it grew.** Throwaway measurement code reached 9 114 lines, nine times the kept code: 286 functions, 28 of them over 50 lines, the longest 338 lines. One file grew from 538 to 1 027 lines in a single commit of review fixes.
- **Reviews only ever added.** Every reviewer agent looks for what is missing (edge cases, invariants, untested behaviour); none looks for what could go. Every finding became code in the same change, also on throwaway code.
- **The size rules were prose.** Files under 400 lines, functions under 60 and changes under 400 lines are written in docs 02, 04 and 07, but no tool checks them. That breaks principle 2 of [01](01-ai-first-principles.md): every rule that matters is checked by a machine.

Outside evidence points the same way:

- Anthropic's prompting guide notes that recent Claude models tend to over-engineer (extra files, unneeded abstractions, flexibility nobody asked for) and gives a counter-prompt ([Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)). Section 2 adopts it.
- GitClear's analysis of 211 million changed lines (2020 to 2024) found copy-pasted lines rising from 8.3 % to 12.3 % of changes and refactored ("moved") lines falling from 25 % to under 10 %, as AI assistants spread ([GitClear 2025](https://www.gitclear.com/ai_assistant_code_quality_2025_research)).
- Google's review guide calls about 100 changed lines a reasonable change and 1 000 usually too large ([small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html)); the SmartBear study at Cisco found reviewers effective on 200 to 400 lines at a time ([SmartBear](https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/)).

## 1. What counts as bloat

- Code that no released requirement, declared tool or test needs.
- Options, parameters and extension points nobody asked for.
- Abstractions, helpers and wrappers used once.
- Checks for states that cannot occur inside trusted code.
- The same logic in two places.
- Dead code: unused functions, arguments, imports, branches.
- Comments that repeat the code or the SPEC; docstrings on private helpers.
- Tests that check the same behaviour again under another name.
- Documents and logs that repeat what another file already says.

Not bloat: validation at the boundaries (public API, file input, kernel entry), tests of released invariants, and the provenance comment that names a source.

## 2. Rules for every agent

These go into `AGENTS.md` (adapted from the Anthropic counter-prompt above):

1. **Scope.** Do only what the task and its requirements ask. No features, refactors or "improvements" beyond them. A bug fix does not tidy the code around it.
2. **Requirements bound the code.** Every function in `src/` serves a released requirement or a declared tool. If something seems needed that no requirement covers, stop and propose a requirement; do not write it.
3. **Validate at the boundary, trust inside.** Check inputs where they enter (public functions, importers, kernel entry points). Inside a module, do not re-check what the boundary guarantees.
4. **No one-use abstractions.** A helper, class or wrapper is created when a second caller exists, not before.
5. **Library before own code.** Use what Clipper2, NumPy, OCCT or the standard library already do.
6. **Comments say why, not what.** Name the requirement or the source; do not restate the code or the SPEC. Docstrings on the public API only.
7. **Deleting is progress.** A change that removes code while every check stays green is welcome. Temporary files and scripts are removed before the task ends.
8. **Report the size.** Every task report ends with one line: lines added and removed in `src/`, `tests/`, `tools/` and spikes, and the module's budget used.

## 3. Limits, checked by tools

The numbers are ours unless a source is named; they are declared tool settings (D-049) and are tuned after the first release, never silently.

| Level | Soft limit (report) | Hard limit (fails) | Checked by |
| --- | --- | --- | --- |
| Change (pull request), non-test code | 200 lines | 400 lines; more only with Peter's label | `tools/size-check` against the base branch |
| File | 400 lines | 800 lines (generated code excepted) | `tools/size-check` |
| Python function | 60 lines (as in [02](02-repository-layout.md) and [04](04-code-conventions.md)) | complexity 10 (ruff `C901`), 12 branches (`PLR0912`), 50 statements (`PLR0915`), 5 arguments (`PLR0913`), 6 returns (`PLR0911`); the pylint defaults ruff uses | ruff in `tools/lint` |
| C++ function | none (clang-tidy can only fail) | 80 lines, 6 parameters (clang-tidy `readability-function-size`), cognitive complexity 15 (`readability-function-cognitive-complexity`; its default is 25) | clang-tidy in `tools/lint` |
| Module | its budget | budget + 20 % | `NLOC` budget per module in `architecture/modules.yaml`, `tools/size-check`; raising a budget is a decision. NLOC counts code lines without comments and docstrings, as lizard does |
| Plan step | its estimate | estimate + 50 %: stop and ask, as for the timebox | the plan and the size line of each report |

A change that adds more than about 50 lines to `src/` without adding or changing a requirement is flagged for review: either a requirement is missing or the code is not needed.

## 4. Duplication, dead code and requirement coverage

- **Duplication:** jscpd (MIT) on `src/` and `tools/`, failing on new clones of 50 tokens or more (`--fail-on-new-clones`; the threshold is ours).
- **Dead code:** vulture (MIT) on `src/` and `tools/` at 80 % confidence or more, with a short whitelist for public API that tests do not call yet; ruff's `ARG` rules for unused arguments.
- **Requirement coverage:** `tools/trace-check` records coverage per test (coverage.py dynamic contexts) and maps each test to its `req` marker. Lines in `src/` that no requirement-tagged test runs are listed. Each such line is either a missing requirement (a SPEC gap to report) or code to delete. Kernels follow once their C++ coverage is measured.
- **Hotspots:** the gardener runs lizard (function length, cyclomatic complexity, C++ and Python) weekly and lists the ten worst functions and every module over 80 % of its budget.

## 5. Reviews that can subtract

- **Every finding gets a class.**
  - *Must fix:* the change breaks a released requirement, an invariant, safety or provenance. Fixed in this change.
  - *Spec gap:* a real risk that no released requirement covers. It becomes a question or a draft requirement, not code in this change.
  - *Nice to have:* recorded in the plan's backlog, no code.
  Only must-fix findings change the code in the same change. This is what stops the growth seen in the stack test app's plan 0001.
- **A simplifier reviewer** (a new agent, `simplifier`) runs on every change over about 100 lines of non-test code. It lists what could go without breaking a requirement: code no requirement needs, one-use abstractions, duplicated logic, checks inside trusted code, options without a requirement, comments that restate. It proposes deletions with the lines saved and never adds anything.
- **Fix rounds are watched.** If a round of review fixes grows the non-test diff by more than 30 %, the change lists which finding each addition answers.
- **Deleting has a legal path.** Removing code together with its tests, because their requirement was withdrawn or changed by a person, is allowed; the test auditor reports it as "removed with REQ-…", not as a weakened test. Weakening a test stays forbidden ([06](06-testing-and-quality-gates.md), rule 2), regression cases are never deleted, and golden outputs change only through a person.

## 6. Throwaway code

Throwaway code (a probe) answers one question with numbers, for a plan's decision.

- It lives in `spikes/<plan>/<step>/`, nothing in `src/` imports it, and it is deleted from the main branch after the plan's decision; a git tag keeps it.
- About 300 lines per question; above 600 the question is too broad: split it, or write kept code under a SPEC.
- One review round, for measurement validity only: does it measure what it claims, and are the numbers reproducible. Robustness findings are recorded, not fixed.
- No tests beyond the probe's own assertions. Each "Done when" is measured once per system; heavy cases run on request.
- The result is a table in the plan's progress log and a README of at most one page with the method and its caveats.

## 7. Lean documents

- A plan's progress entry is at most about 30 lines per session; numbers go into tables. When a plan passes 300 lines, older entries move to an archive file next to it.
- `AGENTS.md` stays under 150 lines and module `AGENTS.md` under 60 ([08](08-agent-instruction-files.md)); nothing is copied from `docs/dev/`.
- A SPEC states its non-goals and an estimated size (lines of kept code and of tests), so a budget exists before the first line is written.

## 8. Where this starts

- **Before the first product code (after the stack test app's plan 0001):** `tools/size-check`, the ruff and clang-tidy limits, the simplifier agent, the finding classes and the report line. They are cheap and they shape the first modules, which every later module copies (principle 7 of [01](01-ai-first-principles.md)).
- **With the second module:** jscpd, vulture and requirement coverage in `tools/trace-check`.
- **For the rest of the stack test app's plan 0001:** only the throwaway-code rules (D-133).

## Sources

- SRC-118 ([sources snapshot](../spike/sources-snapshot.md)): plan 0001 in the stack test app's own repository (`test_repo`), commit c1c21d3, our measurements.
- Anthropic, [Claude prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices), section on over-eagerness in agentic coding.
- GitClear, [AI Copilot Code Quality 2025](https://www.gitclear.com/ai_assistant_code_quality_2025_research).
- Google, [Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html).
- SmartBear, [Best practices for code review](https://smartbear.com/learn/code-review/best-practices-for-peer-code-review/) (the Cisco study).
- Tools: ruff (MIT); clang-tidy (Apache-2.0 with LLVM exception), [cognitive complexity check](https://clang.llvm.org/extra/clang-tidy/checks/readability/function-cognitive-complexity.html); [jscpd](https://github.com/kucherenko/jscpd) (MIT); [vulture](https://github.com/jendrikseipp/vulture) (MIT); [lizard](https://github.com/terryyin/lizard) (licence to be confirmed with T-023); coverage.py dynamic contexts.

---

[Index](README.md) · [← 11. User interface](11-user-interface.md)
