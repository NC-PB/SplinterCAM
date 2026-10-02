---
name: research-to-spec
description: Draft or extend a module SPEC.md from a research section (docs/research/NN). Use when a module has no spec yet, or when new research material must become requirements.
---

# Draft a module spec from research

Input: $ARGUMENTS (a research section number and the target module)

1. Read the research section, the module's row in docs/research/24 (invariants), and the matching group in docs/research/18 (pitfalls). Read nothing else unless the section links to it.
2. Start from `docs/templates/SPEC.md` (in the repository: the existing `SPEC.md`, if any; keep existing IDs).
3. Write requirements in EARS form with new IDs `REQ-<MODULE>-<NNN>`:
   - one per invariant from docs/research/24;
   - one per pitfall from docs/research/18 that applies (each pitfall is a requirement in disguise);
   - one per "trap" in the research section;
   - failure modes as WHEN/IF requirements with a diagnostic code.
4. For each requirement, name how it will be verified (unit, property, golden case).
5. Fill in the tolerance budget, the algorithms (research section and paper per line, no pseudo-code), the test plan and open questions.
6. Do not invent numbers. If the research gives no value for a limit or constant, list it under open questions.
7. Set the status to `Draft` and ask a person to review. Do not implement anything in the same task.
