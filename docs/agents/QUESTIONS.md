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

## AQ-004: model's size, 344 NLOC against the budget 260 (plan 0007, step 3)

- Asked: 2026-10-25, plan 0007 step 3, by the coding agent (headless run)
- Box: 1 (Peter's judgement: `architecture/modules.yaml`, and the Reviewed requirements if they are narrowed)
- Question: the `model` implementation is done and all 29 requirements pass their tests (87 tests in `tests/model/`), but it comes to 344 NLOC (`tools/size-check`) against the budget of 260 (hard limit 312) and the SPEC's estimate of 220. That is 56 % over the estimate, past the 50 % stop of docs/dev/12, section 3, so `tools/check` fails and nothing is pushed. The `simplifier` found about 15 NLOC to remove (applied: 352 to 344) and judged the rest intrinsic to the Reviewed SPEC. The estimate gave `check_job` about 110 NLOC; it is about 230, because of REQ-MDL-029 (a type check on every field, each wrong field skipping only its own checks), REQ-MDL-026 (type errors first, a fixed order, `PARAM_REPEATED` at its position) and REQ-MDL-027 (a location for every element); about 40 NLOC of imports and `__all__` were not in the estimate. For the user nothing changes between the options: both report the same errors for a job file with one mistake. They differ for a job file with several mistakes in one tool or operation:
  - (a) Raise the budget, keep the SPEC: every wrong value is reported at once, as now.
  - (b) Narrow REQ-MDL-029 so that a tool or operation with any field of the wrong type gets only `VALUE_TYPE_INVALID` and none of its other checks: the user fixes the types, runs again, and only then sees range errors. That saves about 30 NLOC, which is just enough for the hard limit of 312 and not for the budget of 260.
- Recommendation: (a). Replace the `model` line of `architecture/modules.yaml` with exactly:
  `  model:                  { layer: 2, kernel: false, depends_on: [foundation], research: ["26", "22", "27", "10", "23"], budget: 360 }`
  and I change the SPEC's size estimate to about 345 NLOC when I resume. The same pull request also passes the change limit: 473 lines of non-test code against 400 (`tools/size-check --change origin/main`; docs/dev/12, section 3). Recommended: the label `large-change` on it, since the module is one unit and splitting the types from `check_job` would leave a first pull request with nothing that checks them. Safe default meanwhile: the work is committed on the branch `model/impl-0007-step3`, not pushed; no requirement is narrowed.
- Status: Answered 2026-10-25
- Answer: (a), as recommended (Peter): `model`'s budget 360 in `architecture/modules.yaml` (applied by the Project Spike session) and the `large-change` label on the pull request. REQ-MDL-029 stays as reviewed. Also (Peter): from step 4 on, size estimates in a SPEC or plan step are about 1.5 times the first count, for the decomposition the strict lint forces; recorded in `docs/plans/active/0007-first-nc-program.md`, Decisions.

## AQ-005: Review of the cl SPEC draft (plan 0007, step 4)

- Asked: 2026-10-25, plan 0007 step 4, by the coding agent (headless run)
- Box: 1 (Peter's judgement: a reviewed SPEC is a human gate; the interface between the strategies and `ncx`)
- Question: `src/splintercam/cl/SPEC.md` (21 requirements, REQ-CL-001 to 021, all Draft) holds the slice's toolpath record: one setup with its work offset, operations with a header (name, note lines, tool, point k and a, spindle speed, tol, feed classes, clearance height) above RAPID, LINE and planar ARC moves with roles LINK, APPROACH, CUT and RETRACT. It refuses a record that breaks its rules, by raising, because the record is written by code, not typed by the user; it does not poll the cancel flag, as its checks are short (DEC-CL-002, a deviation from REQ-FND-013's every module). Four choices change what can reach the machine; please confirm or change each:
  1. **The first move of every operation goes along the tool axis only, and the second stays at the clearance height** (REQ-CL-006, 008, 012): a RAPID to Z with X and Y unchanged, then a RAPID in the plane at or above the clearance height, as research 10 says. After a tool change the tool's position differs per machine, so no move sweeps across the part, or dives diagonally, from an unknown position. A strategy that starts otherwise is refused.
  2. **Every rapid runs at or above its link height, compared exactly** (REQ-CL-011, 012; DEC-CL-004): a rapid that moves in X or Y starts and ends at or above its link height; a rapid along the axis ends at or above it; the operation starts and ends at or above the clearance height. A rapid 0.001 mm below its height is a bug in the strategy and is refused, not let through by a tolerance.
  3. **Spindle CW, coolant on, the tool centre path (no G41/G42) and the XY plane for every operation, without fields** (DEC-CL-003), as in `model` (DEC-MDL-006). The register radius r is not in the record until control compensation comes; the axial offset a is, and the writer shifts every Z by it (D-154).
  4. **A measurement point other than k = 1** (a second point of the tool, D-154) is held in the record as given. NCX has no point words yet (R1-11), so the writer always writes `OFFSET:LEN` with the tool number, the register of the tool's first point; with k = 2 every Z would be written for point 2 while the length register named is point 1's (research 26, trap 3: wrong by the difference). Also in the SPEC, without a choice to make: a full circle must end exactly at its start, and any other arc whose end lies within eps_len (1e-6 mm) of its start is refused, so the control is never sent a tiny arc that prints as a full circle (DEC-CL-006; the writer adds the final check on the printed values in step 6). Recommended: the `ncx` writer (step 6) refuses an operation with k ≠ 1 with a diagnostic naming the operation, until NCX has the point words; point 1 may still have any a, which the writer applies to every Z.
- Recommendation: approve the SPEC as drafted, with 1 to 4 as recommended, once AQ-006 to 008 are answered. Safe default meanwhile: nothing is implemented; DEC-CL-001 to 006 stand as provisional.
- Status: Answered 2026-10-26
- Answer: approved as drafted, with 1 to 4 as recommended (Peter): the first move along the tool axis and the second at the clearance height; rapids at or above their link height, compared exactly; spindle CW, coolant on, tool centre path and the XY plane without fields; the record holds k as given and the `ncx` writer (step 6) refuses an operation with k ≠ 1 with a diagnostic naming the operation until NCX has point words (R1-11). The SPEC is Reviewed; DEC-CL-001 to 004 and 006 stand.

## AQ-006: cl's arc check: depend on geometry2d (plan 0007, step 4)

- Asked: 2026-10-25, plan 0007 step 4, by the coding agent (headless run)
- Box: 1 (Peter's judgement: `architecture/modules.yaml` and an interface between modules)
- Question: the record must refuse an arc whose end does not lie on its circle or does not fit its sweep (research 26, test 1; REQ-CL-016), or the control is sent an arc it computes differently, which cuts a wrong fillet or stops with an error. geometry2d already decides exactly this, the same on every platform (REQ-G2D-042, 043, kernel `check_arcs`, D-055), but only inside `curve_rows`; `cl` depends on foundation alone. Options:
  - (a) `cl` depends on geometry2d, and geometry2d gains a public `check_arc_rows(rows, ctx) -> NDArray[np.int8]` (the status per curve row, as `RowStatus`) over its existing kernel function, in a small geometry2d pull request (SPEC line, wrapper, tests) before cl's implementation. The record checks arcs exactly as io and offset2d build them.
  - (b) `cl` checks arcs itself with NumPy's `sin` and `cos`: no new dependency, but NumPy's trigonometry may differ in the last bit between platforms, so an arc right at the eps_len limit could be accepted on one machine and refused on another (against D-055's first tier), and the rule would exist twice.
- Recommendation: (a). Replace the `cl` line of `architecture/modules.yaml` with the line of AQ-007, which adds geometry2d to `depends_on` (layer 1 below cl's layer 2; no cycle). Safe default meanwhile: the SPEC is written for (a); no code.
- Status: Answered 2026-10-26
- Answer: (a), as recommended (Peter): `cl` depends on geometry2d; geometry2d gains a public `check_arc_rows(rows, ctx)` over its kernel in its own small pull request before cl's implementation.

## AQ-007: cl's budget in architecture/modules.yaml (plan 0007, step 4)

- Asked: 2026-10-25, plan 0007 step 4, by the coding agent (headless run)
- Box: 1 (Peter's judgement: `architecture/modules.yaml`)
- Question: `cl` has no budget. `src/splintercam/cl/SPEC.md`, Size estimate: first count about 205 NLOC, by Peter's rule of 2026-10-25 about 1.5 times that, about 310 NLOC (the plan's 150 times 1.5 is 225; the draft is 38 % over that, within the 50 % stop, for the column checks of DEC-CL-001, the link-height rules and the full-circle and tiny-arc rules the spec review added).
- Recommendation: replace the `cl` line with exactly (with AQ-006 (a)):
  `  cl:                     { layer: 2, kernel: false, depends_on: [foundation, geometry2d], research: ["26", "10"], budget: 310 }`
  or, with AQ-006 (b):
  `  cl:                     { layer: 2, kernel: false, depends_on: [foundation], research: ["26", "10"], budget: 310 }`
  Research 10 is added because the SPEC takes the first move and the link heights from it. Safe default meanwhile: no code, so no size to check.
- Status: Answered 2026-10-26
- Answer: as recommended (Peter): `cl`'s line in `architecture/modules.yaml` is `{ layer: 2, kernel: false, depends_on: [foundation, geometry2d], research: ["26", "10"], budget: 310 }` (applied by the Project Spike session).

## AQ-008: Where the operation's note comes from; model has no field and no room (plan 0007, step 4)

- Asked: 2026-10-25, plan 0007 step 4, by the coding agent (headless run)
- Box: 1 (Peter's judgement: what the user enters; `model`'s Reviewed SPEC and budget)
- Question: plan 0007 step 4 and the feature map, section 6, give an operation a note, written line by line as NCX comments after its name. `cl`'s header holds the note lines (REQ-CL-002), but `model`'s `Operation` has no note field, and `model` is at 358 of its 360 NLOC. Options:
  - (a) `model` gains `note: tuple[str, ...] = ()` on `Operation`, checked by `check_job` (each line a `str`, `VALUE_TYPE_INVALID` otherwise; no control character and no `"`, a new `OP_NOTE_INVALID`, as REQ-CL-017 and RR-005), as REQ-MDL-030 and 031: about 12 NLOC, so `model`'s budget 375 (`  model:                  { layer: 2, kernel: false, depends_on: [foundation], research: ["26", "22", "27", "10", "23"], budget: 375 }`), in its own small pull request. The user writes the note in the job file (step 7) and sees it in the NC program.
  - (b) No note in plan 0007: the header keeps the field, every strategy passes `()`, and the note comes with the desktop app's operation dialog. The NC program shows the operation's name only.
- Recommendation: (b): the slice proves the path to the machine, and a note changes nothing the machine does; (a) when the job file grows. Safe default meanwhile: (b), the note empty in every record.
- Status: Answered 2026-10-26
- Answer: (b), as recommended (Peter): no note in plan 0007; the header keeps the field and every strategy passes `()`. The note gets a source with the job file or the operation dialog.

## AQ-009: geometry2d's budget for `check_arc_rows` (plan 0007, step 4)

- Asked: 2026-10-26, plan 0007 step 4, by the coding agent (headless run)
- Box: 1 (Peter's judgement: `architecture/modules.yaml`)
- Question: AQ-006 (a) gives geometry2d a public `check_arc_rows(rows, ctx)` that returns the `RowStatus` of each curve row, so `cl` refuses an arc before the control gets one it computes differently. geometry2d is at 3986 of its 4000 NLOC (counted as `tools/size-check` counts), which leaves 14 lines. Options:
  - (a) A full status, decided in the kernel (`src/splintercam/geometry2d/kernel/arcs.cpp`, a new binding beside `check_arcs`). `CURVE_INVALID` for a value that is not finite, |sweep| > 2π, or a radius at or below eps_len (an arc row `make_arc` never builds, because it turns such an arc into a line). `ARC_INCONSISTENT` when REQ-G2D-042 or 043 fails. `OK` for a line with finite ends or a consistent arc. Every row gets an answer, and the answer is the same on every platform (D-055). First count about 45 NLOC (kernel function and loop 26, binding 8, header 2, Python wrapper and export 9); by the 1.5 rule about 65. That puts geometry2d at about 4051, over 4000. It needs this line in `architecture/modules.yaml`:
    `  geometry2d:             { layer: 1, kernel: true,  depends_on: [foundation], kernel_interface: [exact.hpp, distance.hpp, grid.hpp], research: ["03"], budget: 4060 }`
  - (b) A thin Python wrapper over the existing `check_arcs`, about 8 NLOC, within the budget. It answers only `OK` or `ARC_INCONSISTENT`, and only under the precondition that every value is finite and 0 < |sweep| ≤ 2π. Outside that the answer is undefined: an arc with sweep 2π + 0.1 whose end fits at 0.1 rad comes back `OK`. `cl` already refuses those rows itself before the check (REQ-CL-014, 017), and it would add REQ-CL-016's radius rule itself with `sqrt`, so the machine gets the same program either way. But a public geometry2d function that answers `OK` for an invalid arc is a trap for the next caller.
- Recommendation: (a), budget 4060. Safe default meanwhile: nothing implemented on branch `geometry2d/check-arc-rows`; the run stopped here, as the task asked.
- Status: Answered 2026-10-26
- Answer: (a), as recommended (Peter): the full status decided in the kernel; geometry2d's budget 4060 in `architecture/modules.yaml` (applied by the Project Spike session).
