# ADR 0008: Deterministic output

- Status: Accepted (2026-09-27, Peter)
- Date: 2026-09-24
- Deciders: Peter Burgener
- Drafted by: Claude

## Context

Golden tests, failure replay and agent debugging all need the same input to give the same output. Parallel code, hash-map iteration and unseeded randomness break this quietly.

## Decision

For the same input, version and settings, every computation produces bit-identical output, independent of thread count. Across macOS, Windows and Linux, output is compared within a tolerance, not bit for bit (accepted this way on 2026-09-27, D-017). Concretely: stable sorts with tie-breakers, no output order from hash maps or addresses, randomness only from a seeded generator in the `Context`, parallel results merged in a fixed order, invariant-culture number formatting. A `deterministic` check in the golden runner runs each case twice (and once with one thread) and compares.

## Consequences

Slightly more care in parallel code. Failures become reproducible, which is what makes unsupervised agent work debuggable.

## Alternatives considered

- Deterministic only with one thread: hides bugs that appear only in parallel runs.

<!-- Citation corrected on 2026-10-11 with Peter's approval: a link to research 18, which is not used in SplinterCAM (D-042, T-019), was removed from the Context. The decision is unchanged. -->
