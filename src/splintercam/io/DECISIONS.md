# Decisions: io

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-IO-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-IO-001: Gaps up to 0.01 mm are repaired; open chains and refused gaps stop the import

- Date: 2026-10-13; decided by: Peter (answer 1 on the SPEC draft, plan 0007, Decisions); the reading for open chains ours
- Status: Active
- Decision: a gap up to the declared limit `dxf_gap_close_mm` = 0.01 mm is repaired with `DXF_GAP_CLOSED` (warning) naming the place. A gap the repair refuses (`DXF_GAP_NOT_CLOSED`) and every open chain (`DXF_OPEN_CHAIN`) are errors naming the place: the import returns no value.
- Why: Peter: "larger gaps stop the import naming the place". An end that meets nothing within the limit is such a gap, so open chains stop the import too (ours, reading the answer). This also prevents the wrong part: with research 21's warning, an outline with a 0.02 mm gap and one hole circle left exactly one closed chain, the circle, which would have been read as the part.
- Rejected: open chains as warnings (research 21, Method 6): a drawing that does not close can then import its only other closed loop. 0.0016 mm (the geometry share at finishing tolerance): exported DXF rarely closes that well (Peter).
- Where: REQ-IO-021, 022, 026; RR-004 item 5.

## DEC-IO-002: Units: a mismatch stops; a file without a unit takes the job's

- Date: 2026-10-13; decided by: Peter (answer 2); the reading for unsupported `$INSUNITS` values ours
- Status: Active
- Decision: a job unit that differs from the file's stops with `DXF_UNIT_CONFLICT`. A file without a unit (`$INSUNITS` missing or 0) follows research 21, Method 2: the job's unit is used, and without one the import stops with `DXF_NO_UNITS` (Peter's corrected answer 2, 2026-10-13). An `$INSUNITS` value io does not read (feet, decimetres, …) stops with `DXF_UNIT_UNSUPPORTED`.
- Why: with the file or the job winning, a one-word mistake cuts a part 10 or 25.4 times too large or too small (Peter). A file in feet states a unit, and no job unit (mm or inch) matches it, so it is a mismatch by answer 2 (ours); research 21 counted such values as "no unit", which would have taken the job's millimetres for feet.
- Rejected: the file wins with a warning; the job wins; other `$INSUNITS` values as "no unit" (research 21, Method 2); a warning when the job's unit is used for a file without one (Peter's first wording of answer 2, withdrawn the same day).
- Where: REQ-IO-005 to 008; RR-004 item 6.

## DEC-IO-003: Chaining: two-stage matching, the junction rule and the move bound

- Date: 2026-10-12; decided by: ours (two spec-review rounds of the draft)
- Status: Active
- Decision: ends are matched in two stages: clusters of ends within eps_len (connected components; three or more ends are a branch), then unique pairs within the gap limit. At a junction the row with the larger magnification D/c keeps its end and the other moves onto it (a line before an arc; ties: the smaller source ID keeps it). Each row's moves are bounded by B = (|ΔP0| + |ΔP1|)·D/c, D = c for |φ| ≤ π and c / sin(|φ|/2) above; silent up to 3·eps_len, a reported gap up to the gap limit, refused above it, all moves of a refused row at once. A branch fails the whole import. Exact duplicate rows are dropped with `DXF_DUPLICATE`.
- Why: research 21's midpoint rule keeps an arc's sweep, so on a 359° arc a 0.005 mm end move shifts the arc by about 0.5 mm (review 1). B is exact: with the sweep kept every arc point is P0 + (P1 − P0)·w, w fixed by φ and the parameter, |w| and |1 − w| ≤ D/c (review 2); |ΔC| + |Δr|, the first try, underestimated above π and refused shallow arcs below it. 3·eps_len is the snapping share of research 01's flattening allowance. Refusing a row's moves together makes the result independent of row order (D-055). A T among the selected entities makes the contour ambiguous; a job naming the part's layer avoids it.
- Rejected: the midpoint (above); bridging a gap with a short line row (adds geometry nobody drew); "within the gap limit" as one stage (counts the far end of a short row as a second candidate, a false branch).
- Where: REQ-IO-017 to 024; RR-004 item 3.

## DEC-IO-004: Names, diagnostic codes and small rules of the SPEC

- Date: 2026-10-12; decided by: ours
- Status: Active
- Decision: the interface names (`read_dxf_contour`, `DxfContour`, `DrawingUnit`, `decode_source_id`); the codes `DXF_UNREADABLE`, `DXF_ENTITY_INVALID`, `DXF_DEGENERATE`, `DXF_DUPLICATE`, `DXF_ENTITY_TOO_LARGE`, `DXF_LAYER_EMPTY`, `DXF_PART_SIZE`, `DXF_GAP_NOT_CLOSED`; an ARC with equal start and end angles is a full circle; the reference z is the value with the most votes, not research 21's "first contour"; each chain starts at its smallest source ID; the diagnostic groups of REQ-IO-029; layer names compared exactly, provisional until the DXF rule is cited at implementation.
- Why: research 21 names none of them; each closes a gap the spec reviews found. The reference z: the first contour is not known before chaining, and a stray entity listed first must not discard the part (RR-004 item 4).
- Rejected: the reference z from the first entity (a stray entity at another z would skip the whole part).
- Where: REQ-IO-002, 010 to 012, 015 to 017, 024, 025, 027 to 029.
