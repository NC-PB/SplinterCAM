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

## DEC-IO-005: Implementation choices of the chain reconstruction (ours)

- Date: 2026-10-25; decided by: ours (plan 0007, step 2 implementation)
- Status: Active
- Decision: four choices the SPEC leaves open at implementation, all box 2 (ours):
  1. **OCS ±z to WCS is computed in io, not through ezdxf's `to_wcs`.** +z is the identity; −z maps x to −x and the elevation's world z to −z and reverses every sweep and bulge, as the arbitrary-axis algorithm gives for extrusion (0, 0, −1) (REQ-IO-009, verified by the mirror tests). This keeps the sweep-sign rule, which is ours, next to the coordinate map.
  2. **Duplicates are found by an order-independent key on a grid of eps_len (coordinates) and eps_ang (sweep)**, not by an O(n²) pairwise scan (REQ-IO-017). Exact duplicates land in the same bucket. A pair that straddles a grid boundary is not seen as a duplicate; it is then a stage-1 cluster of ≥3 ends and reported as `DXF_BRANCH`, which is safe (no wrong part), not silent.
  3. **End matching uses a full O(n²) distance matrix in NumPy**, and the walk, the duplicate keys and the junction bookkeeping are Python loops over rows. This is the provisional chaining (research 21, Method 5, until topic 25 releases its chaining); the slice's drawings hold tens of entities (io SPEC, Performance budget). geometry2d's kernel does the per-point work (arc construction, bounding boxes); io does none.
  4. **`DXF_NO_UNITS` reports a loose bounding box** of the raw points in drawing units, with each arc's centre ± radius added, computed without building arc rows (the rows need eps_len in mm, which is not known without a unit). It is enough to tell a 100-unit part from a 4-unit one (REQ-IO-006).
  5. **Every tolerance decision uses sqrt of a sum of squares, never `hypot` or `sin`** (D-055, SPEC split rule): end-matching distances, the move bound B, degeneracy lengths and the ±z-parallel test. The magnification D/c for |φ| > π is written as 2r/c, not 1/sin(|φ|/2), since the chord c = 2r·sin(|φ|/2) makes them equal with no transcendental. ARC and CIRCLE end points still come from `math.cos`/`sin` once per entity, which the SPEC's split rule allows.
  6. **io's two test modules disable four pyright rules** (`reportUnknownMemberType`, `reportUnknownArgumentType`, `reportUnknownVariableType`, `reportPrivateImportUsage`) at file level, because ezdxf's factory stubs carry `Unknown` in their signatures; the rules that catch real type-logic errors stay on under strict mode.
  7. **`DXF_LAYER_EMPTY` fires only when the selected layer holds no entity of a read type at all**; a read-type entity that is on the layer but later rejected (non-planar, invalid) counts as "a read entity on the layer", so the import reports that rejection (and then `DXF_CONTOUR_COUNT`), not `DXF_LAYER_EMPTY` (REQ-IO-025, ours).
- Why: the SPEC's split rule puts per-point loops in the kernel and leaves the chain bookkeeping to Python (SPEC, Public interface, split rule); it fixes the chaining as provisional. These choices stay inside that and inside the tolerance budget. The sqrt-only rule (choice 5) is the determinism rule D-055 the first spec review of the implementation flagged.
- Rejected: ezdxf's `to_wcs` for the mirror (hides the sweep-sign rule); an O(n²) duplicate scan (needless for the slice and still O(n²)); building rows twice to get the no-unit box in mm.
- Where: `src/splintercam/io/_entities.py`, `src/splintercam/io/_chain.py`; REQ-IO-006, 009, 017, 018.
