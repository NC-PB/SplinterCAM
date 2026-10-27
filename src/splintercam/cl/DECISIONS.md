# Decisions: cl

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-CL-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-CL-001: Moves as columns of NumPy arrays

- Date: 2026-10-25; decided by: ours (SPEC draft, plan 0007 step 4); part of Peter's review (AQ-005), since it is the interface the strategies and `ncx` use
- Status: Accepted 2026-10-26 (SPEC Reviewed, AQ-005)
- Decision: an operation's moves are seven arrays with one row per move (`kind`, `role`, `end_mm`, `centre_mm`, `sweep_rad`, `feed_class`, `link_height_mm`), not a tuple of move objects. Fields a kind does not use hold a fill value (NaN, 0 or `NO_FEED_CLASS`), as geometry2d's curve rows hold a line's centre as NaN (REQ-G2D-188). Feed classes are an index into the header's (name, mm/min) pairs.
- Why: AGENTS.md's split rule puts loops over points and segments into the kernel or vectorised NumPy; the record's checks are such loops, and a 3D finishing operation has hundreds of thousands of moves. The XY part of a move and its predecessor is a curve row, so the arc check can reuse geometry2d's (AQ-006).
- Rejected: one frozen dataclass per move kind (checks and the writer become Python loops over moves; about 100 bytes and an object per move); a single (n, k) float array (kinds and indexes as floats, no dtype per column).
- Where: REQ-CL-003, 004, 021.

## DEC-CL-002: A broken record raises `ValueError`

- Date: 2026-10-25; decided by: ours
- Status: Accepted 2026-10-26 (SPEC Reviewed, AQ-005)
- Decision: `make_operation` and `make_cl_data` raise `ValueError` naming the operation, the first breaking move's index from 0 and the requirement ID; they return no `Result` and no diagnostics.
- Why: the record is written by strategies, which is code; every user value has been checked before, by `model`'s `check_job` (DEC-MDL-003). A broken record is a programming error, as an invalid `ParameterDeclaration` is in model (REQ-MDL-018). Expected outcomes are the strategy's diagnostics, before a record exists. Naming the first rule broken (in requirement order) and its first move keeps the message short and fixed (D-055). `make_cl_data` checks every operation again, because a `ClOperation` built directly is unchecked; the cost is one more vectorised pass. Neither function polls `ctx.cancel` (REQ-FND-013 asks a module to return `CANCELLED`, but the checks are short and return no `Result`; `ctx` gives eps_len only).
- Rejected: diagnostics per broken move (a user cannot fix a strategy's bug, and a `Result` makes every reader handle a case that cannot occur in a correct program); no checks (the writer would put a wrong arc or a low rapid on the machine without a word).
- Where: REQ-CL-004 to 020.

## DEC-CL-003: Spindle CW, coolant on, CENTER and XY without fields; tol kept

- Date: 2026-10-25; decided by: ours, from research 26's subset and Peter's approval of DEC-MDL-006 (AQ-002)
- Status: Accepted 2026-10-26 (SPEC Reviewed, AQ-005)
- Decision: the header has no spindle direction, coolant, `comp_mode`, plane or `control_tol` field. The SPEC states CW, coolant on, CENTER and XY for every operation of the slice; `ncx` writes `SPINDLE=CW`, `COOLANT=ON` and `WORKPLANE=XY` and no `TOLERANCE` words (research 26 subset, trap 11). Without CONTROL mode the register radius r has no effect on the written path, so the header carries the point's k and a only. The header does carry `tol` (research 26, operation header): the writer needs the operation's rounding allowance, 0.1·tol (REQ-FND-009, D-149; `.claude/rules/ncx.md`), and should not have to look the operation up in `model` (spec review).
- Why: `model` has no such fields either (DEC-MDL-006); a field that accepts one value is code no requirement needs (docs/dev/12, section 1). Adding a field with a default later does not break a producer.
- Rejected: one-member enums for direction and plane; copying `tol` for a later `TOLERANCE` word (research 26 subset: not written in plan 0007).
- Where: REQ-CL-002.

## DEC-CL-004: Exact comparisons for heights and planar arcs

- Date: 2026-10-25; decided by: ours
- Status: Accepted 2026-10-26 (SPEC Reviewed, AQ-005)
- Decision: the link-height and clearance-height checks compare z ≥ h exactly, and a planar arc's end z must equal its start z exactly. Only the tiny-arc rule (REQ-CL-014) and the arc's circle and sweep (REQ-CL-016) use eps_len.
- Why: the producer copies the same float into the height and the move's z (research 10, Method 5: h_c for moves at the clearance height), so equality is exact without a tolerance; a rapid even 1e-9 mm below its link height is a producer bug, and a tolerance would let it through. An arc with a tiny travel would be a helix, which the slice does not have and the writer would need `IZ` for.
- Consequence for producers: whether a rapid changes x or y is decided exactly too, so the rapid up from the approach point P must copy P bit for bit; one ulp off, it counts as a move in the plane and raises when it starts below its link height (a test pins this; a pitfall for the module's `AGENTS.md`).
- Rejected: eps_len on every comparison (allows a rapid below its height and a near-helix to pass unseen).
- Where: REQ-CL-011, 012, 015.

## DEC-CL-005: Name and note are the operation's comments; note characters provisional

- Date: 2026-10-25; decided by: ours, reading plan 0007 step 4 ("comments, operation name and note") with the feature map, section 6 (Peter, 2026-10-07)
- Status: Accepted 2026-10-26 for plan 0007 (AQ-008 (b): the note is empty); the character rule is aligned with research 27, trap 15 (RR-005) when the note gets a source
- Decision: the header holds the operation's `name` (NCX `SECTION`, and the first comment line of the operation by the feature map) and its `note` as lines (further `COMMENT` lines). The slice has no other comments: the register comment of research 26 comes with CONTROL mode. A note line is refused if it holds a control character (below U+0020 or U+007F), which would break the NCX line, or `"`, which ends the quoted string, until RR-005 says how NCX quotes. Other characters, umlauts included, pass: research 27's Comments row says NCXchange transliterates them in comments and warns `CMP022` where it cannot. The name keeps model's rule, ASCII letters, digits and underscores (REQ-MDL-012).
- Why: the feature map names the user's name as the first comment and the note as further comments. Where the note comes from is open: `model` has no note field (AQ-008); until then the strategy passes `()`.
- Rejected: a general list of comments with no meaning (the writer could not place the register comment later); refusing non-ASCII in notes (stricter than NCXchange needs; a shop writes notes in German).
- Where: REQ-CL-002, 017.

## DEC-CL-006: Full circles exact, tiny arcs refused, reversed arcs checked by the producer

- Date: 2026-10-25; decided by: ours (spec review of the draft)
- Status: Accepted 2026-10-26 (SPEC Reviewed, AQ-005; the arc check through geometry2d, AQ-006 (a))
- Decision: an ARC with |sweep| equal to 2π (the double nearest it) must end exactly at its start; an ARC with a smaller |sweep| must end more than eps_len from its start. geometry2d's arc rules (REQ-G2D-042, 043) are applied with r = |S − C| as `check_arcs` does; an arc the producer reversed is checked in the direction it is written, by the producer, before it builds the record.
- Why: research 26 maps a full circle as the centre form with end = start. A full circle whose end is up to eps_len off prints one NCX step (D-149) away from its start, which NCX reads as a near-zero or near-full arc. A tiny arc (sweep 1e-7 rad at r = 5) passes `check_arcs` but prints with end = start, and the control cuts a full circle; geometry2d's `make_arc` turns such arcs into lines (REQ-G2D-047), but rows from `curve_rows` and offset2d may still hold them. The eps_len floor is a sanity check of the record, not a guarantee: eps_len equals the NCX step (1e-6 mm, D-149), so an end up to √2·eps_len away can still print equal to the start, and NCXchange rounds again to the machine. The guarantee belongs to the writer, which refuses an arc whose printed ends are equal (`ncx`, step 6), and at the machine's resolution to NCXchange (D-149). `check_arcs` is not symmetric in S and E (the angle tolerance is eps_len / |S − C|), and geometry2d's `AGENTS.md` warns that a reversed arc may be invalid input; a valid DXF arc right at the limit could otherwise raise from inside the strategy.
- Rejected: a symmetric rule with r = min(|S − C|, |E − C|) (a second arc rule beside geometry2d's, against AQ-006's point); eps_len for the full circle's end (the writer's problem above).
- Where: REQ-CL-014, 016; the interface's preconditions.

## DEC-CL-007: Readings of the SPEC's wording in the implementation

- Date: 2026-10-27; decided by: ours (implementation, plan 0007 step 4)
- Status: Accepted
- Decision: (a) REQ-CL-014's "the end is the start bit for bit" for a full circle, and REQ-CL-011's "whether x or y changes", compare the values of x and y exactly, so −0.0 equals +0.0. (b) REQ-CL-017 checks the ranges of fields of the right type, field by field and lazily, so a later field of the wrong type cannot hide an earlier field's refusal. A field of the wrong type is not checked as such: a `None` name or a str feed raises the `TypeError` Python gives, a feed pair of three items the `ValueError` of tuple unpacking without a requirement ID, and a str note (`("Rohteil")`, the comma missing) passes as one line per character. A column that is a subclass of `np.ndarray` (a masked array) is refused by REQ-CL-004, though: a masked NaN would pass REQ-CL-007 unseen (spec review). (c) An operation of one move, a RAPID along the axis to the clearance height or above, passes: no requirement refuses it.
- Why: (a) −0.0 and +0.0 are the same point; the writer prints both as 0 (`.claude/rules/ncx.md`: no "-0"), so the full circle prints with end = start and the vertical rapid stays vertical. A comparison of the bits would refuse a producer that computed one end as −0.0, for no effect on the machine. (b) `ClHeader` is typed; pyright strict, which every producer passes, rejects each of these (a str is not a `tuple[str, ...]`), and REQ-CL-017 names ranges only. Checking types too would cost lines of the 310-line budget for errors the type checker already finds. (c) REQ-CL-006 and 012 hold for it; `ncx` writes the tool call and nothing else.
- Rejected: comparing bits with `view(np.int64)` (refuses equal points); type checks per field as model's `check_job` does (that module checks user input, DEC-MDL-003; this one checks code).
- Where: REQ-CL-011, 014, 017; `_moves.py`, `_header.py`.

## DEC-CL-008: Plan 0007's links as a rule of the record; the retract height in the header

- Date: 2026-10-27; decided by: Peter (AQ-018 (c)); the range of the retract height and the exact comparisons ours
- Status: Accepted
- Decision: `ClHeader` gains `retract_height_mm` (h_r). REQ-CL-022 refuses a RAPID that changes x or y and starts or ends below the clearance height, and any RAPID that ends below h_r, whatever its link height. It runs after REQ-CL-016 (REQ-CL-020: by ID). h_r must be finite and not above the clearance height; equal is allowed. The comparisons, and whether x or y changes, are exact, as DEC-CL-004's.
- Why: REQ-CL-011 checks a RAPID only against the link height the producer writes. A producer bug that copies the target z into the link height passed `cl`, and the writer would have put a diagonal G0 into the stock on the machine (cnc-reviewer, AQ-018). Research 10, Method 1 to 5, gives plan 0007's links: rapids in the plane at h_c, the descent at P to h_r, so `cl` can refuse anything else without knowing the stock. Research 10 test 1, against the stock, stays in step 5. h_r below h_c follows research 10 (h_c = stock top + 5, h_r = stock top + 3); equal is harmless for every rule and keeps the range simple.
- Rejected: leaving it to step 5 alone (AQ-018 (a): one bug in the producer would reach the writer unchecked); a link height restricted to {h_c, h_r} (the same protection with a rule on a value instead of on the move, and no protection for a RAPID whose link height is right but whose z is not).
- Consequence: a later plan with rapids in the plane below h_c (D-087) replaces REQ-CL-022 by a new SPEC entry. `strategies/profile` passes h_r into the header.
- Where: REQ-CL-017, 020, 022; `_types.py`, `_header.py`, `_moves.py`.
