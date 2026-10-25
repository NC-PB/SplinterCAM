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

## AQ-002: Review of the model SPEC draft (plan 0007, step 3)

- Asked: 2026-10-25, plan 0007 step 3, by the coding agent (headless run)
- Box: 1 (Peter's judgement: a reviewed SPEC is a human gate; interfaces between modules)
- Question: `src/splintercam/model/SPEC.md` (29 requirements, REQ-MDL-001 to 029, all Draft) holds the slice's job data: one flat end mill with its measurement points, a box stock, one setup with its work offset, the operations with their parameter values, checked once by `check_job`. Four choices change what the user enters or sees; please confirm or change each:
  1. **The drawing's frame is the work frame** (DEC-MDL-002). The setup has no placement: the DXF's origin is the datum of work offset 1, and the part sits where it is drawn. With a placement, the user could move the datum without editing the DXF, but the profile would have to transform the contour, a path the slice does not test. Recommended: no placement in the slice, as plan 0007's scope says ("the part at the origin").
  2. **Spindle CW and coolant on for every operation, without fields** (DEC-MDL-006). The user cannot switch coolant off or run a left-hand tool. With a direction field, a CCW spindle would turn the climb profile into conventional milling unless the profile refuses it. Recommended: no fields in the slice.
  3. **A measurement point's axial offset a must lie between 0 and the flute length** (DEC-MDL-004, provisional). A shop that measures a flat end mill above its flutes gets `TOOL_POINT_INVALID` and must measure at the tip. Without the limit, a typing error in a (10 for 1.0) shifts every Z of the program by that amount (research 26, test 10). Recommended: keep the limit; it can be widened when tool assemblies come.
  4. **The parameter declarations live in model** (DEC-MDL-001): each strategy declares its parameters (name, unit, default or none, range, source) with model's `ParameterDeclaration`, and `check_job` refuses a job with a missing, misspelt, repeated or out-of-range value, naming it. Numbers only in the slice (mm, mm/min, dimensionless); the panel fields of docs/dev/11 come with the desktop app. Recommended: as drafted.
- Recommendation: approve the SPEC as drafted, with 1 to 4 as recommended. Safe default meanwhile: nothing is implemented; the draft's choices stand as provisional.
- Status: Answered 2026-10-25
- Answer: SPEC approved with 1, 2 and 4 as recommended (Peter). Item 3 changed (Peter, as Project Spike recommended): D-154 says the user can enter any point, so the axial offset a is any value ≥ 0, not limited to the flute length; a above the flute length is accepted with a warning (not an error) that names the shift of every Z, for example "every Z is output 40 mm above the tip", so a typing error is seen; the setup sheet states the point (D-151). Apply item 3 to `src/splintercam/model/SPEC.md` and DEC-MDL-004, then mark the SPEC Reviewed; recorded in `docs/plans/active/0007-first-nc-program.md`, Decisions.

## AQ-003: model's budget and research list in architecture/modules.yaml

- Asked: 2026-10-25, plan 0007 step 3, by the coding agent (headless run)
- Box: 1 (Peter's judgement: `architecture/modules.yaml`)
- Question: `model` has no budget, and its research list names topic 23 (cutting data), which the slice does not use; the SPEC builds on topics 26, 22, 27 and 10. The SPEC estimates about 220 NLOC (`src/splintercam/model/SPEC.md`, Size estimate), 10 % over the plan's 200 because of the type checks the spec review added. Without a budget, `tools/size-check` cannot hold the module to its estimate.
- Recommendation: replace the `model` line with exactly:
  `  model:                  { layer: 2, kernel: false, depends_on: [foundation], research: ["26", "22", "27", "10", "23"], budget: 260 }`
  (23 kept for the cutting data that comes later). Safe default meanwhile: no code, so no size to check.
- Status: Answered 2026-10-25
- Answer: as recommended (Peter); applied to `architecture/modules.yaml` by the Project Spike session.
