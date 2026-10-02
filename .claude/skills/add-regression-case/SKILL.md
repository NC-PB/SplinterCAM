---
name: add-regression-case
description: Turn a failure dump, a failing property-test seed or a bug report into a minimal permanent regression case under testdata/regressions. Use when a bug has been reproduced or a failure file exists.
---

# Add a regression case

Input: $ARGUMENTS (a failure file from `failures/`, a property-test seed, or an issue number)

1. Reproduce the failure: `tools/replay <failure-file>`, or rerun the property test with the seed.
2. Minimise the input (`tools/replay --minimise` where available; otherwise remove geometry step by step while the failure persists). Smaller is better: a handful of segments beats a whole part.
3. Create `testdata/regressions/<issue-id>-<short-name>/` with `case.json` (operation, parameters, tolerances, checks), the minimal input file, and `README.md` (what failed, which requirement it violates, the issue link, source and licence of the data).
4. Add the case to `testdata/LICENSES.md`.
5. Add or extend the test that runs the case, tagged with the violated requirement ID. Confirm it fails.
6. Stop here unless the task also asks for the fix; then continue with the `implement-requirement` skill.
7. Never include customer or proprietary geometry. Redraw a minimal equivalent instead.
