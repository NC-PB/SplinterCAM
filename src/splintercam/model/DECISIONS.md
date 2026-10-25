# Decisions: model

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-MDL-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-MDL-001: Parameter declarations live in model; numbers only in the slice

- Date: 2026-10-25; decided by: ours (SPEC draft, plan 0007 step 3); the place is an interface between modules, so it is part of Peter's review (AQ-002)
- Status: Active (approved by Peter, AQ-002, 2026-10-25)
- Decision: model defines `ParameterDeclaration` (name, unit, default or none, a range with open or closed ends, source) and checks an operation's values against its strategy's declarations in `check_job`. Each strategy declares its own parameters with this type; model knows no strategy. Values are float64 in the internal unit; the slice's units are mm, mm/min and dimensionless (research 22's air gap 0.2·R, D-079, is a factor because a default cannot depend on R). An operation's values are (name, value) pairs, so a checked job is immutable and its order is part of equality. An invalid declaration raises `ValueError`: it is code, not user input.
- Why: docs/dev/03 says every strategy declares its parameters once and a new strategy changes nothing else in the code base; strategies (layer 3) and job (layer 5) both depend on model (layer 2), so model is the lowest module both see. Research 22's parameters need what foundation's `DeclaredParameter` lacks: no default (step-down and feeds, "the job gives them"), and exclusive ends (feeds > 0, step-down > 0).
- Rejected: reusing foundation's `DeclaredParameter` (default required, inclusive ends only, no name; it describes the tolerance defaults file and changing it is a foundation SPEC change for no gain); a typed `ProfileParameters` class in model (strategy knowledge in a lower module; every new strategy would change model); declarations without a shared type, one per strategy (job could not check them uniformly, and D-018's generated panels need one form); the panel fields of docs/dev/11 (group, label, tooltip, basic flag, visibility) now: no user interface in the slice, they come with `apps/desktop`; enums and geometry slots: the slice's profile needs none (climb only, research 22); rad and 1/min as units before a parameter uses them (spindle speed is an operation field); a `Mapping` of values (a dict inside a frozen dataclass stays mutable and unhashable, and its equality ignores order; spec review).
- Where: REQ-MDL-017 to 024.

## DEC-MDL-002: The part's frame is the work frame; no placement in the slice

- Date: 2026-10-25; decided by: ours, from Peter's slice scope (plan 0007: "one setup with work offset 1 and the part at the origin"); asked in AQ-002
- Status: Active (approved by Peter, AQ-002, 2026-10-25)
- Decision: `Setup` has no placement. Every coordinate of the job (the drawing, the stock, the operation's heights) is in the work frame, which is the drawing's frame. Research 26's 4×4 `placement` comes with the plan that brings several setups or a datum away from the drawing's origin.
- Why: research 26's subset sets the placement to the identity; a field that only accepts the identity is code no requirement needs (docs/dev/12, section 1), and a general transform would need the profile to transform the contour, a path the slice does not test.
- Rejected: a 4×4 transform that accepts only the identity; a general rigid transform now; a translation-only origin (the user moves the drawing's origin in CAD instead, as the slice's job file names the DXF as drawn).
- Where: REQ-MDL-009.

## DEC-MDL-003: One check at the boundary, every diagnostic collected

- Date: 2026-10-25; decided by: ours
- Status: Active
- Decision: the types are plain frozen dataclasses that accept any values; `check_job` checks the whole job once, Python types included, and returns every diagnostic, with a value only when there is no error, in a fixed order with a location per element. A field of the wrong type skips its other checks, and a tool with an invalid dimension skips its point checks, so no diagnostic reports a comparison against NaN.
- Why: the spec review showed that JSON's `true` reaches Python as `True`, which is an `int` and would pass as tool number 1, diameter 1 or tol 1 mm, and that a string value would make `math.isfinite` raise instead of reporting. The values come from a job file the user wrote, so wrong ones are expected outcomes and become typed diagnostics, not exceptions (AGENTS.md, Rules). Cross-checks (an operation's tool and point, duplicate numbers and names) need the whole job anyway. A user fixing a job file wants all its errors at once, as io reports every entity (REQ-IO-029).
- Rejected: checks in `__post_init__` raising `ValueError` (user input is not a programming error; it would stop at the first); a `make_…` function per type (more interface, the cross-checks still need a job-level check); stopping at the first error.
- Where: REQ-MDL-025 to 027.

## DEC-MDL-004: A point's axial offset is any a ≥ 0; above the flute length a warning

- Date: 2026-10-25; decided by: Peter (AQ-002, item 3, as Project Spike recommended), changing the draft's limit
- Status: Active
- Decision: a measurement point's a is any finite value ≥ 0 and its r lies in [0, R]; otherwise `TOOL_POINT_INVALID` (error). An a above the flute length is kept, with `TOOL_POINT_ABOVE_FLUTE` (warning) naming the point and the shift of every Z ("every Z is output 40 mm above the tip").
- Why: D-154 says the user can enter any point, so a shop may measure a flat end mill above its flutes. Research 26 test 10 shifts every Z by a, so a mistyped a (10 for 1.0) moves every depth of the program by the same amount; the warning names that shift so the error is seen, and the setup sheet states the point (D-151). r ≤ R is D-154 ("r is not larger than the radius that cuts"), and on a flat end mill R cuts along the whole flute.
- Rejected: a limited to [0, flute length] with an error above it (the draft's provisional rule: it refuses points D-154 allows); any a ≥ 0 without a warning (a typing error would pass unseen); negative a (a point below the tip is in air; D-154 measures from the tip up).
- Where: REQ-MDL-006.

## DEC-MDL-005: Tool numbers and operation names are unique; no upper limits

- Date: 2026-10-25; decided by: ours
- Status: Active
- Decision: tool numbers are at least 1 and unique in the job; work offsets at least 1; operation names unique in the job, made of ASCII letters, digits and underscores. No upper limit on tool number, work offset or spindle speed.
- Why: a T number names one tool; two tools under one number would put the wrong length into the program. NCXchange's messages are mapped back to the operation by its section name (plan 0007, step 6), which needs unique names. The character set is research 26's program-name condition, which the slice applies to every name it writes. Upper limits are the machine's and NCXchange reports them (D-148; research 27, Datum row: G54 to G59, G54.1 P, G505 to G599 differ per controller); the magazine check needs the sidecar (research 27).
- Deviation: research 27's Comments row transliterates umlauts in operation names; the slice refuses them instead (`OP_NAME_INVALID`). Stricter and safe: the user sees the name the program will carry.
- Rejected: T0 as "no tool" (some controls read T0 as an empty spindle; nothing in the slice needs it); a name length limit (no source gives one; NCXchange reports it if a control has one).
- Where: REQ-MDL-002, 004, 010, 012, 013.

## DEC-MDL-006: Spindle CW and coolant on, without fields, in the slice

- Date: 2026-10-25; decided by: ours, from research 26's subset ("`spindle` CW, `coolant` on"); asked in AQ-002
- Status: Active (approved by Peter, AQ-002, 2026-10-25)
- Decision: an operation holds its spindle speed only; the direction is clockwise and coolant is on for every operation of the slice, written so by `ncx` (step 6).
- Why: research 22 bases climb milling on a clockwise spindle: a CCW field would let the user reverse the cut's side without the profile knowing. No slice operation needs coolant off.
- Rejected: a direction field the profile would have to refuse when CCW; a coolant flag with no consumer.
- Where: REQ-MDL-011.

## DEC-MDL-007: The operation tolerance is checked by foundation

- Date: 2026-10-25; decided by: ours
- Status: Active
- Decision: `check_job` passes each operation's tol to `ToleranceSet.for_operation` and reports its errors at the operation; only a non-finite tol, for which `for_operation` raises, gets model's own `OP_TOL_INVALID`.
- Why: the tol range (tol_min to 1 mm) is foundation's (REQ-FND-009, 010); a second copy of it in model could drift.
- Rejected: tol as a declared parameter of each strategy (every strategy would repeat it, and job needs it to build the `Context`); model's own range check.
- Where: REQ-MDL-016.

## DEC-MDL-008: Measurement points are numbered 1 to n in order; a job needs an operation

- Date: 2026-10-25; decided by: ours (spec review)
- Status: Active
- Decision: a tool's points carry the numbers 1, 2, …, n in the order given, so the default point 1 is the first (D-154) and k names the same point in the NCX and on the setup sheet. A setup without operations is refused with `SETUP_NO_OPERATION`.
- Why: D-155 fixes only "1 for the tool's first point"; gaps or a reordered list would make "the first point" and "point 1" differ. A job without operations would reach `ncx` as a program without moves.
- Rejected: free numbering with uniqueness only (two meanings of "the default point"); an empty job as a valid result (no step of the slice needs it).
- Where: REQ-MDL-005, 009.
