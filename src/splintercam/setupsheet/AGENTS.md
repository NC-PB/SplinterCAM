# AGENTS.md: setupsheet

Layer 4. The setup sheet of one NC program (plan 0009): `make_setup_sheet` computes a frozen
`SetupSheet` from the checked job, the `cl` record, the part's contour and the file names;
`render_html` (step 3) prints it. Contract: `./SPEC.md`. Why it is built this way:
`./DECISIONS.md` (read it before changing behaviour). Public API: `./__init__.py`. No C++ part.
Depends on: foundation, geometry2d (`row_boxes`, `CurveRows`), model, cl. Writes no file (`job`
does, AQ-058).

## Commands

- `tools/test-one setupsheet`

## Invariants that must never break

- D-148: no machine or controller data here; every number comes from the job, the record, the
  contour or the file names.
- REQ-SHT-001 (DEC-SHT-004): the sheet describes the program that was written. A header field the
  sheet prints that the job also holds is compared, exactly, before anything is computed.
- REQ-SHT-011: the within-R refusal is toolpath REQ-TP-012's expression in its order, in scalar
  Python floats, so a record toolpath accepted is never refused here by rounding.
- D-055 tier 1: decisions use comparisons, sums and products; NumPy reductions only `min`, `max`,
  `np.minimum.at` and counts; `sqrt` only for printed distances and u. No clock, locale or
  environment (a unit test greps the sources for the imports).
- Values are unrounded; rounding for print is `render_html`'s alone (REQ-SHT-017).

## Known pitfalls

- "Same XY" is exact with +0.0 equal to −0.0. `np.unique` compares the bytes of rows, so keys get
  `+ 0.0` first (turns −0.0 into +0.0); the value kept and printed is the first one met, taken
  from the record, not from the key.
- Move 1's start XY is unknown (NaN): comparisons with it are False, which is what "along Z
  alone" and "below h_c" need; do not replace NaN by 0 or by move 0's end.
- An approach point above the stock top is not checked against R (REQ-SHT-011 applies where the
  tool comes down below the top); toolpath still refuses it.
- `register_radius_mm` comes from the job's tool point, not from `ClHeader`, until pull request
  97's header field is merged (DEC-SHT-011); then compare it in REQ-SHT-001 as a is compared.
- Test records live in `tests/support/setupsheet_cases.py`; its golden P is at Y −11 (air gap
  0.2·R), not the Y −15 of `cl_strategies.P`.
