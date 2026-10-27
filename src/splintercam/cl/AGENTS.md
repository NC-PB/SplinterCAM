# AGENTS.md: cl

Layer 2. The neutral toolpath record for plan 0007 (one setup; RAPID, LINE and planar ARC moves
in XY; the tool centre at the tip), checked by `make_operation` and `make_cl_data`. Contract:
`./SPEC.md`. Why it is built this way: `./DECISIONS.md` (read it before changing behaviour).
Public API: `./__init__.py`. No C++ part. Depends on: foundation, geometry2d (`check_arc_rows`).

## Commands

- `tools/test-one cl`

## Invariants that must never break

- REQ-CL-020: the header's fields first, in the order of `ClHeader`; then the move rules in ID
  order, as listed in `_moves.py`'s `_RULES`. A new rule goes into its ID's place there, so a rule
  only ever sees rows that passed the rules before it (REQ-CL-016 relies on it).
- REQ-CL-019: the record holds read-only copies; `make_cl_data` rebuilds every operation, so an
  operation built directly never reaches `ncx` unchecked (REQ-CL-018).
- REQ-CL-021, D-055: no NumPy trigonometry in a decision. The arc rules are geometry2d's
  `check_arc_rows`; here only comparisons and `sqrt`.
- DEC-CL-004: heights and an arc's z are compared exactly; eps_len only in REQ-CL-014's tiny-arc
  rule and REQ-CL-016.

## Known pitfalls

- DEC-CL-004: whether a RAPID changes x or y is exact. The rapid up from the approach point P must
  copy P's x and y bit for bit; one ulp off, it counts as a move in the plane and raises
  REQ-CL-011 when it starts below its link height. Copy the same float into a link height and the
  move's z, never a recomputed one.
- Move 1 always counts as a move in the plane (its start's x and y are unknown): its link height
  must not lie above move 0's z, and move 1 must end at the clearance height or above (REQ-CL-012).
- DEC-CL-006: an arc is checked in the direction it is written, and the check is not symmetric in
  start and end (the angle tolerance is eps_len / |S − C|). A producer that reverses an arc
  (climb) checks it after reversing.
- A full circle (|sweep| = `math.tau`) must end exactly at its start; any other arc more than
  eps_len from it (DEC-CL-006).
- A wrong type in a header field is outside REQ-CL-017 (DEC-CL-007 (b)): a `None` name raises
  `TypeError`, and a str note (`("Rohteil")`, the comma missing) passes as one line per
  character. Only pyright strict in the producer catches these.
- The note rule (DEC-CL-005) lags research 27, trap 15: `(` and `)` in a note must be refused
  before the note gets a source (Fanuc ends the comment at `)`). Harmless while the note is
  always `()` (AQ-008); a SPEC change when it is not.
- Property tests take the `ctx` fixture with `HealthCheck.function_scoped_fixture` suppressed, as
  geometry2d's do; `Context` is frozen.
