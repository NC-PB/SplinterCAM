---
name: implement-requirement
description: Implement or fix one module requirement (REQ-…) test-first, from spec to evidence. Use when a task names a requirement ID or asks to add or change a module's behaviour.
---

# Implement one requirement

Requirement: $ARGUMENTS

1. Find the requirement in `src/splintercam/**/SPEC.md`. If it is missing, ambiguous or not `Reviewed`, stop: draft or clarify it and ask a person to approve it.
2. Read that SPEC, the module's `AGENTS.md`, and only the research section the requirement cites. Check `docs/plans/active/` for a plan that covers it.
3. For interfaces of other modules, read `docs/generated/api/<module>.md`, not their source.
4. Write the test first. Name or tag it with the requirement ID. Include the messy inputs the research warns about (docs/research/18 for the module's area).
5. Run `tools/test-one <module>`. Confirm the new test fails, and fails for the expected reason.
6. Implement the smallest change that makes it pass. Run `tools/test-one <module>` after each step. Follow the patterns of the existing code and the glossary names.
7. Run `tools/check`. For geometry or toolpath changes, run `tools/render` on the affected zoo cases and look at the images.
8. Run the `test-auditor` subagent on the diff; for algorithm changes also `spec-reviewer`; for CL, post or G-code changes also `cnc-reviewer`. Fix what they find.
9. Update the SPEC ("Verified by", status), the plan's progress log, and the glossary if you added a term.
10. Report: files changed, tests added, commands run with results, renders produced, open questions.

Never weaken an existing test to make the new one pass. If two requirements conflict, stop and ask.
