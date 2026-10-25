# Agent questions

The mailbox between coding agents and the people and sessions that answer them (docs/dev/07, "Questions: who answers"). An agent writes a question here, commits it, keeps working where it can, and names the open entries when it stops. The Project Spike session answers box 2 and 3 questions from the research, brings box 1 questions to Peter and writes his answer here; the agent resumes from this file. Each question and its answer stay in one entry, so a new session can take over without the conversation that raised it.

Rules:

- Look first. Before writing an entry, search Project Spike (`~/project_spike` when it is readable: `DECISIONS.md`, `research/`, `sources/register.md`; otherwise `docs/spike/` and `docs/research/`). An answer found there is used and cited, not asked.
- Box 1 (Peter's judgement) and anything that blocks the step go here. A box 2 choice is decided by the agent in the module's `DECISIONS.md`, not asked. A box 3 gap in the research is a research request in `docs/research/REQUESTS.md`; this file only links to it when the step waits on it.
- IDs are AQ-NNN, never reused. Entries are not deleted; an answered entry keeps its question and gains the answer. The answer is recorded where it belongs as well (the plan's Decisions, `DECISIONS.md`, a SPEC), and the entry names that place.
- Name every file by its path from the repository root.

Entry format:

```
## AQ-NNN: <short title>

- Asked: <date>, <plan and step>, by <who>
- Box: 1 (Peter's judgement) | 2 (blocking technical choice) | 3 (research, RR-NNN)
- Question: <in machining terms for box 1: what happens on the machine or for the user under each option>
- Recommendation: <the agent's answer, and the safe default taken meanwhile>
- Status: Open | Answered <date>
- Answer: <the answer, by whom>; recorded in <path>
```

## AQ-001: io's size budget

- Asked: 2026-10-25, plan 0007 step 2, by the coding agent (headless run)
- Box: 1 (Peter's judgement: `architecture/modules.yaml`)
- Question: `io` came to 795 NLOC against its budget of 360 (hard limit 432), for the 30 reviewed requirements of `src/splintercam/io/SPEC.md`: the gap repair with its move bound, five OCS entity types, exact diagnostics. Raise the budget, or split the chaining into a module of its own?
- Recommendation: raise the budget to 820; a split needs a new SPEC for no gain in the slice.
- Status: Answered 2026-10-25
- Answer: budget 820 (Peter); recorded in `architecture/modules.yaml` and `docs/plans/active/0007-first-nc-program.md`, Decisions.
