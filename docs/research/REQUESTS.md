# Research requests

<!-- Box 3 questions (docs/dev/07, "Questions: who answers"): knowledge nobody has at hand. Agents add a request here
     instead of asking Peter; Project Spike answers it with sources (D-159: research is pulled by a plan step).
     Newest last. IDs RR-NNN are never reused. Files by their path from the repository root. -->

## RR-<NNN>: <short title>

- Date: <YYYY-MM-DD>; raised by: <plan NNNN, step n>
- Question: <what must be known, one or two sentences>
- Why it matters: <the requirement or decision it blocks or makes provisional>
- What is known: <research section, tests or measurements so far, with paths>
- Provisional choice: <the conservative option taken meanwhile, DEC-… marked provisional>
- Status: Open <or: Answered on <date>, see <research section or DEC-…>>

## RR-001: A stock update that errs toward more stock

- Date: 2026-10-08; raised by: plan 0005, SPEC draft (spec-reviewer round)
- Question: how must `remove_machined` subtract a machined region from a stock layer so that the result never loses stock that is really there, and by how much must the machined region be shrunk first?
- Why it matters: REQ-OFF-032 in `src/splintercam/offset2d/SPEC.md` is blocked by it; stock layers decide safe links and skipped air passes (D-026, D-062).
- What is known: `docs/research/02-offsets-and-booleans.md`, Booleans, shrinks the machined area by 3u before the difference. But the shrink is itself a Clipper2 call on an already rounded region, against "offsets are never chained" (same section, D-132), and each of the two calls moves points by up to 2.83u in no fixed direction (SRC-118), so 3u does not cover both. Options seen: a larger margin (at least about 3u + 2·2.83u); or the machined region built from its source paths, grown by t − margin in one call, so nothing is chained.
- Provisional choice: none; REQ-OFF-032 stays out of plan 0005's steps until answered. The other Booleans do not depend on it.
- Status: Open
