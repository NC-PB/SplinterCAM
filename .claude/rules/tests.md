---
paths:
  - "**/tests/**"
  - "testdata/**"
  - "benchmarks/**"
---

# Rules for tests and test data

- Tag every test with the requirement ID it verifies: `@pytest.mark.req("REQ-OFF-003")`.
- Never delete, skip or weaken a test, remove an assertion, or loosen a tolerance or time limit to make it pass. Stop and explain instead.
- Compare geometry with tolerances, Hausdorff distance, loop counts and areas; never exact floats or text diffs of G-code.
- Property tests print their seed on failure and stay under about 2 s each with default case counts.
- Every new file in `testdata/` needs an entry in `testdata/LICENSES.md` (source, licence). No non-commercial or all-rights-reserved data.
- Never write to `testdata/golden/`; use `tools/golden-diff` and let a person approve.
