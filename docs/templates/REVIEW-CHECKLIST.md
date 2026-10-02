# Review checklist

For the person reviewing a pull request, whether an agent or a person wrote it. Tick what applies; a "no" is a request for changes.

## Scope

- [ ] The PR does one thing, names its requirement IDs, and stays within one module (or follows an approved feature spec).
- [ ] Non-test code is small enough to review properly (about 400 lines at most).

## Spec and tests

- [ ] Every new or changed behaviour has a requirement in the SPEC, and a test tagged with its ID.
- [ ] No test was deleted, skipped or weakened; no tolerance or time limit was loosened. If one was, the PR explains why and I agree.
- [ ] The module's invariants are covered by property tests, including messy inputs.
- [ ] Golden changes are explained, with renders, and I have looked at them.

## Numerics

- [ ] Units are clear in names or types; mm and radians inside.
- [ ] No literal epsilons or magic numbers; constants are named and cite their source.
- [ ] Tolerance use stays within the module's budget.
- [ ] Output is deterministic (ordering, randomness, parallel merges).

## Structure and readability

- [ ] Dependencies follow `architecture/modules.yaml`; no new `utils` dumping ground.
- [ ] Names match the glossary.
- [ ] I would understand this code in a year without the PR description.
- [ ] Comments explain why and cite the research section or paper.
- [ ] Errors are not swallowed; expected outcomes come back as diagnostics.

## Machine safety (when CL data, links, posts or G-code change)

- [ ] No rapid below the safe envelope; retracts along the tool axis first.
- [ ] Arcs are valid after rounding; planes and directions are right.
- [ ] Feeds and spindle values have the right units and modes.
- [ ] Controller-specific behaviour is backed by a manual reference, not a guess.

## Provenance and licences

- [ ] No copied code from GPL, LGPL, proprietary or unlicensed sources; permissive snippets are attributed in `NOTICE`.
- [ ] New dependencies have an ADR and pass the licence check.
- [ ] New test data has an entry in `testdata/LICENSES.md`.

## Docs

- [ ] SPEC status, plan progress log and glossary are updated.
- [ ] If an agent made a mistake the instruction files should have prevented, I added a line (or a check) for it.
