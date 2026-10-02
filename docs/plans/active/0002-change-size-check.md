# Plan 0002: The per-PR change limit

<!-- Lives in docs/plans/active/ while work is ongoing, then moves to docs/plans/completed/.
     The agent updates the progress log at the end of every session, before stopping. -->

- Goal: CI reports a pull request that adds more than 200 lines of non-test code against its base branch and fails one over 400, unless it has the label `large-change` (docs/dev/12, section 3; Peter, 2026-10-02).
- Specs: none; a tool, specified by `docs/dev/12`, section 3 and `tools/README.md`
- Research: none
- Branch: one branch and one pull request
- Owner: Peter Burgener; agents: Claude Code cloud sessions
- Status: draft (plan 0001, step 5); starts when Peter releases it

## Context

- `tools/size-check` checks files, functions and module budgets since plan 0001, step 3; the change row of section 3 is the one it does not check yet.
- Workflows are CI configuration: an agent drafts the change as `docs/plans/active/0002-workflow.patch` and Peter applies it. The patch adds a separate workflow, `change-size.yml`, so that adding or removing the label re-runs only this check, not the three-system matrix of `check.yml`.

## Steps

<!-- Each step has a size estimate (kept code and tests). At 50 % over it, stop and ask, as for a timebox
     (docs/dev/12, section 3). -->

- [ ] 1. **`tools/size-check --change <base>`**: count the lines added by `git diff --numstat <merge base>...HEAD` in non-test code (removed lines do not count), report over 200 and fail over 400; `--large-change` turns the failure into a report that names the label. Non-test code: every file except tests (`tests/`, `testdata/`), Markdown and generated files (docs/dev/04 header); a pull request that changes only those passes without a count. Binary files (numstat `-`) are named, not counted. Without `--change`, `tools/check` keeps its present behaviour, so local runs do not depend on a base branch. Tests in `tests/tools/test_size_check.py` with a temporary git repository: under, at and over both limits, the label, a change that removes many lines, a Markdown-only and a generated-only change, a test-only change, a renamed file. Update `tools/README.md`. Size: about 60 lines of kept code + 80 of tests.
- [ ] 2. **Workflow** (Peter): apply `docs/plans/active/0002-workflow.patch`, create the label `large-change` in GitHub, and make the `change-size` check required on `main` if wanted. The agent checks the run on its next pull request and records the result here. Size: the patch, 35 lines.

## Decisions

- 2026-10-02: the label `large-change` lifts the hard limit; the soft limit is still reported (Peter, plan 0001, step 5).
- 2026-10-02: only added lines of non-test code count, as docs/dev/12 says; removed lines do not, since deleting code is what the lean rules want. A pull request that changes only Markdown or generated files is skipped; tests are excluded anyway (Peter). A moved file counts once, through git's rename detection.

## Progress log

<!-- Newest first. What was done, what tools/check reported, what is next. At most about 30 lines per session. -->

### 2026-10-02, plan 0001, step 5

- Drafted this plan and `0002-workflow.patch` (`git apply --check` passes). Nothing implemented.
- Peter's answers, same day: added lines only; Markdown-only and generated-only pull requests are skipped. Step 1 and the decisions follow them.

## Backlog

## Blockers
