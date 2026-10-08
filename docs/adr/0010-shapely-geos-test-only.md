# ADR 0010: shapely and GEOS as a test-only differential reference

- Status: Accepted (Peter, 2026-10-09)
- Date: 2026-10-08; accepted 2026-10-09
- Deciders: Peter Burgener
- Drafted by: Claude Code (plan 0005, DEC-OFF-003)

## Context

D-060 (accepted 2026-09-28) names shapely/GEOS, for tests only, and point-sampling oracles as the independent checks for offsets and Booleans. [Research 02](../research/02-offsets-and-booleans.md), test 20, compares the offset regions of test 10 against shapely/GEOS buffers with round joins, as point sets outside the band. Peter's answer 3 on the offset2d SPEC (`src/splintercam/offset2d/DECISIONS.md`, DEC-OFF-003) asks for this ADR; `docs/dev/09-dependencies-licensing-provenance.md` requires one for every new dependency and for every LGPL one.

Licence facts, checked 2026-10-08:

- shapely is BSD-3-Clause (PyPI JSON metadata, `https://pypi.org/pypi/shapely/json`, field `license_expression`, version 2.2.0; the GitHub README, `https://github.com/shapely/shapely`, says the same).
- GEOS is LGPL-2.1 (the same README links `https://libgeos.org` for it; the PyPI metadata lists a `LICENSE_GEOS` file next to shapely's own, which is the sign that the wheels carry GEOS). That the binary wheels ship GEOS as a bundled shared library is from shapely's installation documentation as we know it; it was not confirmed by the pages fetched and should be checked once when the group is added.

So installing shapely brings an LGPL-2.1 library with it. `docs/dev/09` lets LGPL in only as a separate, dynamically loaded library the user can replace, listed in `NOTICE`, with an ADR. Those conditions are about distributing it; this ADR keeps GEOS out of everything SplinterCAM distributes.

## Decision

shapely (and with it GEOS) is allowed for tests only (Peter, 2026-10-09).

- It goes into a dependency group named `test-oracle` in `pyproject.toml`, beside `dev`, pinned in `uv.lock`. Never into `[project] dependencies`, never into an optional extra of the application.
- `tools/bootstrap` installs the group, so every development setup and CI can run test 20; no test skips for a missing shapely.
- It is never packaged: the Briefcase build installs no dependency groups, so `test-oracle` stays out of the application (`docs/dev/09`; Briefcase per plan 0001).
- Only files under `tests/` import it. Its first use is test 20 of offset2d, in the last step of plan 0005 (after the point-sampling oracles of tests 2 and 9).
- It is a reference, not a source: no code or algorithm is taken from GEOS; the differential test only compares outputs.
- No `NOTICE` entry: GEOS is not distributed, so there is nothing to give notice of. If that ever changes, this ADR is superseded first.
- `tools/licence-check`, when it is written, accepts an LGPL licence in the lock file only for packages that belong to the `test-oracle` group, and fails on LGPL anywhere else.
- Applying this ADR touches `pyproject.toml`, `uv.lock` and `tools/bootstrap`; that is a separate change, in plan 0005's last step.

## Consequences

- An independent implementation checks the offsets as point sets (D-060), which our own oracles cannot do: they share our reading of the definitions.
- Every developer machine and CI job carries GEOS as a test library; it never reaches a user.
- Packaging must keep installing no dependency groups; a check that shapely and GEOS are absent from the built application belongs with the packaging work.
- Nothing under `src/` may import shapely. `tools/arch-check` already enforces this: `tools/lib/arch_python.py` (`_external`) reports "external-allowlist: shapely is not listed under external" for any import of a package not listed under `external` in `architecture/modules.yaml`, and shapely is not listed. Do not add it there. The rule reads `src/` only; a test importing shapely outside `tests/` is a review matter.
- If shapely were ever shipped, GEOS would need the LGPL conditions of `docs/dev/09`; this ADR does not allow that.

## Alternatives considered

- No external reference: only our own oracles. Weaker; an error in how we read the offset definition would appear in both the code and the oracle.
- A hand-written oracle only: the point-sampling oracles of tests 2 and 9 exist anyway and come first. They check against the definitions, but they are ours, and sampling is weak near the band edge. test 20 adds a library nobody here wrote.
- Another library: Clipper2 through a Python binding is excluded by D-060 (the same algorithm as our kernel, not independent); CGAL is GPL; Boost.Geometry is not reachable from Python without a binding and shares no independence benefit worth a build dependency.
- shapely as a runtime dependency: GEOS would ship. Rejected (DEC-OFF-003).
- The group optional, installed only in CI, with test 20 skipping elsewhere: rejected by Peter (2026-10-09), so the test runs everywhere.
- Other group names (`reference`): `test-oracle` says what it is for (Peter).
