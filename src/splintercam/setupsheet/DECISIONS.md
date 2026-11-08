# Decisions: setupsheet

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-SHT-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-SHT-001: A new module at layer 4 writes the sheet's content and HTML; `job` writes the file

- Date: 2026-11-08; decided by: proposed (ours), for Peter (AQ-057: a new module and `architecture/modules.yaml` are his)
- Status: Proposed
- Decision: a new module `setupsheet`, layer 4, depends on foundation, geometry2d, model and cl. It computes a `SetupSheet` value and renders it as HTML; it writes no file. `job` gains it in `depends_on`, calls it after a clean `ncx` run and writes the file (AQ-058).
- Why: the sheet needs the checked job (tools, stock, work offset) and the record (approach points, heights, feeds), both layer 2, so layer 3 or 4 fits; it does not plan, and it sits beside `ncx` as the second output of a program, so layer 4. docs/dev/03, rule 5: only `job` reads and writes files. `job` is at 518 of its 520 NLOC (AQ-039), and the sheet is about 390 by the 1.5 rule.
- Rejected: inside `job` (budget; `job` runs the chain and computes nothing of its own, its SPEC's non-goal); inside `ncx` (`ncx` writes NCX and runs the binary, `architecture/modules.yaml`'s comment; the sheet is not NCX and must not depend on whether `ncx` is present); layer 3 (it plans nothing; a strategy must never import it).
- Where: SPEC header; AQ-057.

## DEC-SHT-002: The reach below h_c comes from the record, not from the strategy's formula

- Date: 2026-11-08; decided by: ours
- Status: Active (draft)
- Decision: the region where clamps must not stand is the XY box of every tool-centre position of moves at or below h_c, grown by R, from the lowest move end to h_c (REQ-SHT-012), computed from the `cl` record for every strategy.
- Why: AQ-035 item 2's "band of t + 2R round the part" and AQ-015 item 1 (a)'s "R + 0.2·R of the stock's sides" are the profile's formulas and both miss the approach point: on the golden job P lies at Y −11, so the tool's edge reaches Y −16, while the band ends at Y −15 and AQ-015's figure at Y −11 (the spec review's table, AQ-056 item 1). The record holds every move the machine makes, so the box holds the tool for every strategy, including later ones, with no strategy-specific code. A box is conservative inside it (the part's own area is inside it, where no clamp can be anyway). The margin round it is Peter's number (AQ-056 item 1; 5 mm provisional, the band's margin over the tool's edge), so the sheet prints both the reach and the keep-clear box.
- Rejected: the band per strategy (misses P; a formula per strategy); the exact swept outline (a polygon the operator cannot check with a ruler; offset2d for no gain at the slice's parts); the reach alone with no margin (narrower than the band Peter approved on three sides).
- Where: REQ-SHT-012; Example parts.

## DEC-SHT-003: A witness mark where a straight approach meets the cut

- Date: 2026-11-08; decided by: ours
- Status: Active (draft)
- Decision: a witness mark is stated where a CUT follows a LINE of role APPROACH that moves in XY, at the CUT's start S and at S + R·u, on the wall or on the allowance left on it, distinct by S and u, with the number of passes (REQ-SHT-015).
- Why: AQ-016 item 7: with no lead arc the part shows a mark at S on every pass. Reading it from the roles keeps it strategy-neutral: a later strategy with a tangent lead arc has an ARC approach and gets no such line, and the profile with P equal to S (REQ-PRF-017, d = 0) has no approach LINE and no mark at that point, which is right: it goes down beside the stock onto the path.
- Rejected: a flag from the strategy (a new `cl` field for one line of text); a mark at every pass start whatever the approach (wrong for lead arcs).
- Where: REQ-SHT-015.

## DEC-SHT-004: A job and record that disagree raise `ValueError`

- Date: 2026-11-08; decided by: ours
- Status: Active (draft)
- Decision: `make_setup_sheet` checks that the record's work offset, operation names and order, and each header's tool, point, a and spindle speed match the job, and raises `ValueError` naming the first mismatch (REQ-SHT-001); likewise for broken file names (REQ-SHT-002) and an approach within R of the stock box (REQ-SHT-011, decided with toolpath REQ-TP-012's own expression, so a record toolpath accepted is never refused by rounding). It reports no diagnostics.
- Why: both inputs were checked where they entered (`model`, `cl`); a mismatch is a bug in `job`, as `cl` treats a broken record as its producer's bug (DEC-CL-002). A sheet that describes another program than the one written is worse than no sheet: the operator trusts it.
- Rejected: a diagnostic (an expected outcome it is not); no check (the sheet would print the job's tool while the program calls another).
- Where: REQ-SHT-001.

## DEC-SHT-005: No cancel poll

- Date: 2026-11-08; decided by: ours
- Status: Active (draft)
- Decision: neither function polls `ctx.cancel`.
- Why: both are vectorised and short (the performance budget is 50 ms at 10 000 moves), as `cl` (DEC-CL-002); `job` polls before and after the stage.
- Rejected: a poll per operation (no measurable gain).
- Where: Public interface.

## DEC-SHT-006: File names only on the sheet

- Date: 2026-11-08; decided by: ours
- Status: Active (draft)
- Decision: the sheet names files by their names, never with folders; a name with `/` or `\` is refused (REQ-SHT-002).
- Why: the sheet is printed and passed on; a folder of the programmer's computer means nothing at the machine and may show a user name. The same job gives the same sheet on every computer (REQ-SHT-019). The files lie next to the sheet (AQ-058).
- Rejected: absolute paths (as `JOB_INPUTS` reports them for the programmer; not for the operator).
- Where: REQ-SHT-002.

## DEC-SHT-007: No date or clock on the sheet; hand-fill fields instead

- Date: 2026-11-08; decided by: ours, the fields asked in AQ-056
- Status: Active (draft)
- Decision: the sheet reads no clock; material, programmer and date are empty fields filled in by hand.
- Why: D-055: the same input gives the same output, which the golden tests and the review rely on. The job file holds no material or programmer yet (feature map, section 8 lists them in the header).
- Rejected: the date of the run (two runs differ; a date injected through `Context` is a foundation change for one field).
- Where: REQ-SHT-004, 019.

## DEC-SHT-008: Printed numbers round toward the safe side

- Date: 2026-11-08; decided by: ours
- Status: Active (draft)
- Decision: three decimals, rounded from the float64's exact binary value with Python's `decimal`; limits round so the printed limit is never less safe than the computed one: reach and keep-clear boxes outward, floors and lowest ends down, gaps down, and the blank limit printed as a coordinate (stock face plus or minus the gap) rounded toward the stock; the stock box and other values to the nearest 0.001 mm (REQ-SHT-017).
- Spec review: rounding the stock box outward and the gap down separately can combine unsafely (face −5.0004, gap 1.0004: the tool's edge at −6.0008, but −5.001 and 1.000 printed allow a blank to −6.001); printing the limit coordinate itself avoids that. A scaled float (`ceil(x·1000)/1000`) prints 4.35 as 4.351, so `decimal` is used.
- Why: the operator checks clamps against the printed number. A reach maximum of 110.0004 printed as 110 would place a clamp at 110 inside the tool's reach by 0.0004 mm; outward rounding cannot do that. Three decimals are far finer than a clamp or a blank is placed by hand, and match the 0.001 mm the dry-run checklist and the golden case's notes use.
- Rejected: one rounding rule for all (unsafe at limits); more decimals (noise on paper).
- Where: REQ-SHT-017.

## DEC-SHT-009: An approach point's lowest end counts its own RAPIDs

- Date: 2026-11-08; decided by: ours (plan 0009, step 2)
- Status: Active
- Decision: an approach point's `lowest_mm` is the lowest end of the RAPIDs counted at it and of the moves along Z alone ending there (REQ-SHT-010).
- Why: the Reviewed wording took the moves along Z alone only, which leaves the value undefined where a RAPID below h_c ends at P after a move that is not along Z alone (`cl` accepts such a record; `toolpath` writes none). Counting the RAPIDs keeps the value defined for every record `cl` accepts and can only lower it, the safe side for the stock-top test of REQ-SHT-011 and the printed floor. On every record `toolpath` writes the two readings give the same number (the RAPID to h_r at P is along Z alone).
- Rejected: `lowest_mm` optional (a third state for the renderer and the operator with no case that needs it); the RAPIDs only (misses the plunge, the point of the value).
- Where: REQ-SHT-010; `src/splintercam/setupsheet/_approach.py`.

## DEC-SHT-010: An operation of one RAPID ends at no known XY

- Date: 2026-11-08; decided by: ours (plan 0009, step 2)
- Status: Active
- Decision: `SheetOperation.end_xy_mm` is None where the last move's end has no XY, which happens only for an operation of one RAPID (move 0, `cl` REQ-CL-006: (NaN, NaN, z)).
- Why: `cl` accepts that operation (SPEC, Example parts); it stays at the tool-change position, whose XY the record does not know. None says so; NaN would reach the renderer as "nan".
- Rejected: NaN in the tuple (prints as text an operator cannot use); refusing the operation (`cl` accepts it, and the sheet is no second check of the record, SPEC Non-goals).
- Where: Public interface; REQ-SHT-016.

## DEC-SHT-011: Each operation names its point k, a and r (AQ-051)

- Date: 2026-11-08; decided by: Peter (AQ-051, superseding AQ-059 item 2), applied by us in step 2
- Status: Active
- Decision: `SheetOperation` carries the operation's point number k, its axial offset a and its register radius r, as the program's comment before the tool change names them; a and r come from the job's tool point k, after REQ-SHT-001 checked that the header's k and a equal the job's. REQ-SHT-008's sentence says the program names k and a only in a comment.
- Why: AQ-051 allows k ≠ 1 and a ≠ 0 with a comment in the program; a length measured to another point moves every Z by the difference, so the operator must read the same k and a on the sheet next to each operation, not only in the tool list. r is not in the header today (pull request 97 adds the register radius to `ClHeader` in a parallel lane), so it is read from the job.
- Rejected: k and a in the tool list only (the operator reads an operation's line at the tool change); r from the header (not there yet; when it is, REQ-SHT-001 can compare it as it compares a).
- Where: REQ-SHT-008, 009; Public interface.
