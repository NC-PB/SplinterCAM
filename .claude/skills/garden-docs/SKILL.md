---
name: garden-docs
description: Check documentation health and report problems (broken links, stale plans, untested requirements, oversized instruction files, glossary drift). Use on a schedule or when asked to tidy the docs.
---

# Garden the documentation

Produce a report first. Make no edits unless the task says so, and never edit accepted ADRs.

Check and report:

1. Broken links and anchors in `docs/`, `src/splintercam/**/SPEC.md`, `AGENTS.md` files.
2. `tools/trace-check` output: requirements without tests, tests with unknown IDs.
3. Plans in `docs/plans/active/` without a progress-log entry in the last 14 days.
4. Specs marked `Implemented` with requirements still `Draft`, and specs older than their module's last code change by more than a month.
5. Instruction files over their size limits (root `AGENTS.md` 150 lines, module `AGENTS.md` 60, `CLAUDE.md` 40, rules 40, skills 80) and rules duplicated between `AGENTS.md` and `docs/dev/`.
6. Names used in code that are synonyms of glossary terms (for example `sideStep` for `stepover`).
7. Gotchas in `AGENTS.md` that a check now enforces (candidates for deletion).

Output a short table: finding, file, suggested fix, effort. Then ask which fixes to make.
