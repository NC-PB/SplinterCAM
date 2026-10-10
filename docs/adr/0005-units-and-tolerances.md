# ADR 0005: Internal units and the tolerance model

- Status: Accepted (2026-09-27, Peter)
- Date: 2026-09-24
- Deciders: Peter Burgener
- Drafted by: Claude

## Context

Unit mix-ups and scattered epsilons are among the most common CAM bugs ([RESEARCH 01](../research/01-foundations.md)). Agents in particular write literal `1e-6` wherever a comparison fails.

## Decision

- Internal units: millimetres and radians, 64-bit floating point. Conversion happens only at the edges (import, UI, post).
- Missing values are represented by an optional type or NaN, never by a magic number.
- All tolerances come from a `ToleranceSet` passed in the `Context`: length and angle epsilons, the operation's chord tolerance, and the share of it each stage may use (tessellation, offset, fitting, controller smoothing; [RESEARCH 11](../research/11-path-optimisation.md)).
- Each tolerance use states which side the error may fall on (inside or outside material), following [RESEARCH 01](../research/01-foundations.md).
- Literal epsilons in code are rejected by a lint.

## Consequences

Every function that compares geometry needs the context; this is deliberate. Tolerance budgets become part of each module spec and are testable.

## Alternatives considered

- Metres as the internal unit: common in physics code, but CAM data, tools and G-code are in millimetres, so every value would be converted twice.
- A global epsilon: simple, and the source of most "works on my part" bugs.

<!-- Citation corrected on 2026-10-11 with Peter's approval: a link to research 18, which is not used in SplinterCAM (D-042, T-019), was removed from the Context. The decision is unchanged. -->
