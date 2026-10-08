[Index](README.md) · [← 05. Specs, plans and decisions](05-specs-plans-decisions.md) · [07. Agent workflow →](07-agent-workflow.md)

# 06. Testing and quality gates

Tests are the sensors that let agents work unsupervised between reviews. RESEARCH 24 (Project Spike) lists what to test (the invariants per module, reference parts and datasets); this document fixes where tests live, when they run, and the rules agents must follow around them.

## Test kinds and locations

| Kind | Location | Purpose |
| --- | --- | --- |
| Unit | `tests/<m>/unit/` | Exact expected values for primitives and small functions |
| Property | `tests/<m>/property/` (Hypothesis) | The module's invariants on thousands of random and deliberately messy inputs |
| Golden | `testdata/zoo/`, runner in `tests/job/golden/` | Whole operations on reference parts, compared geometrically with approved outputs |
| Regression | `testdata/regressions/<issue>/` | Minimised failures; never deleted |
| Differential | `tests/<m>/differential/` | Same question answered by an independent library (Clipper2, OpenCAMLib, a G-code interpreter) |
| End-to-end | `tests/apps/cli/` | Job file → G-code → independent parser → simulated stock → compared with the part |
| Architecture | `tools/arch-check` | `modules.yaml` rules: Python imports, kernel includes, OCP and PySide6 only where allowed |
| Traceability | `tools/trace-check` | Every reviewed requirement has a test; lines in `src/` that no requirement's test runs are listed |
| Size | `tools/size-check` | Change, file and module size limits ([12](12-lean-code.md), section 3) |
| Duplication and dead code | jscpd and vulture in `tools/lint` | New copied code and unused code ([12](12-lean-code.md), section 4) |
| Licence | `tools/licence-check` | SPDX headers, dependency licences, test-data licences |
| Performance | `benchmarks/` | Time budgets from the specs |

## Gates

| Gate | Runs | Must finish in | Contents |
| --- | --- | --- | --- |
| Edit hook | After every file edit by an agent | seconds | Format the file |
| `tools/test-one <m>` | Whenever the agent wants | under 30 s | Unit and property tests of one module, default case counts |
| `tools/check` | Before an agent reports a task as done; pre-commit | under 5 min | Format check, lint (with the function limits, and from the second module on duplication and dead code), build, tests of changed modules and their dependents, size, architecture, traceability, licence checks |
| CI on every PR | Automatically, on Windows, macOS and Linux | under 20 min | Everything above for all modules, golden zoo, end-to-end, docs link check, performance budgets; on Linux also the kernels built with ASan and UBSan running the whole pytest suite |
| Nightly | Scheduled | hours | Property tests with 100× cases, fuzzing of importers and parsers, mutation testing of `foundation` and `geometry2d`, large datasets |

"Keep quality left": the fast checks catch most problems while the agent is still working; CI is the backstop, not the first line.

## Rules agents must follow

1. **Test first for new behaviour.** Write the test, tag it with the requirement ID, run it, see it fail for the expected reason, then implement.
2. **Never weaken a test to make it pass.** No deleting or skipping tests, no removing assertions, no loosening tolerances, no raising time limits, no changing expected values in unit tests without saying why. If a test looks wrong, stop and explain in the plan and the PR; a person decides. The `test-auditor` subagent checks every diff for this. One exception: a test removed together with code whose requirement a person withdrew or changed is not weakened; the `test-auditor` reports it as "removed with REQ-…" ([12](12-lean-code.md), section 5). Regression cases are never deleted.
3. **Golden outputs change only through a person.** An agent runs `tools/golden-diff <case>` and shows the difference (numbers and a render). Only a person runs `tools/golden-approve`, which is denied to agents in the settings.
4. **Flaky tests are bugs.** A test that fails sometimes is fixed or quarantined with an issue the same day, never retried until green.
5. **Property tests print their seed.** A failure is reproduced from the seed, shrunk to a minimal case, and saved as a regression case with the `add-regression-case` skill.
6. **Look at the geometry.** For any change to geometry or toolpaths, run `tools/render` on the affected cases and look at the pictures before reporting; attach them to the PR.

## Comparing geometry

- Never compare coordinates for exact equality or G-code as text.
- Compare curves by Hausdorff distance within the case tolerance, loops by count, orientation and area, toolpaths by swept-area difference, number of retracts and cycle time within a percentage.
- Each `case.json` states the tolerances and the checks to run, so the comparison rules are data, not code:

```json
{
  "id": "pocket-island-touching-wall",
  "input": { "part": "part.dxf", "units": "mm" },
  "operation": { "strategy": "pocket", "parameters": { "stepover": 4.0, "allowance": 0.2 } },
  "tool": { "type": "flat", "diameter": 10.0 },
  "tolerance": { "chord": 0.01 },
  "checks": ["no-gouge", "coverage", "max-stepover", "deterministic"],
  "golden": { "cl": "expected/cl.json", "hausdorffMax": 0.005, "cycleTimeTolerancePercent": 2 },
  "source": "drawn for this project; Apache-2.0",
  "research": ["04", "24"]
}
```

## Coverage

Line coverage is reported but is not a target; agents reach any percentage with empty tests. What counts is requirement coverage (100 % of reviewed requirements, checked by `tools/trace-check`), its reverse (lines in `src/` that no requirement-tagged test runs, each a missing requirement or code to delete; [12](12-lean-code.md), section 4) and, for the numerical core, the mutation score from the nightly run, which shows whether the tests would notice a wrong sign or a wrong comparison.

## Test data

Every file in `testdata/` has an entry in `testdata/LICENSES.md` with its source and licence. Allowed: own drawings, public domain, CC0, CC BY (with attribution), MIT or BSD datasets such as MFCAD and MFCAD++. Not allowed in the repository: non-commercial data (Fusion 360 Gallery), data whose creators keep all rights (ABC dataset), and anything from the old commercial system. Large files go through Git LFS.

---

[Index](README.md) · [← 05. Specs, plans and decisions](05-specs-plans-decisions.md) · [07. Agent workflow →](07-agent-workflow.md)
