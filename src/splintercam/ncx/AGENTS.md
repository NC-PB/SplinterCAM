# AGENTS.md: ncx

Layer 4. Writes a checked toolpath record (`cl`) as one program of canonical NCX, the same for
every machine (D-148), and runs the pinned `ncx` binary on it: `format --check`, `check
--strict`, `compile`. Contract: `./SPEC.md`. Why it is built this way: `./DECISIONS.md` (read it
before changing behaviour). Public API: `./__init__.py`. No C++ part: the printer and the blocks
are NumPy over the record's columns. Depends on: foundation, cl.

## Commands

- `tools/test-one ncx`
- The real `ncx` test (`tests/ncx/integration/test_real_ncx.py`) needs `ncx` on the path and
  `SPLINTERCAM_NCXCHANGE` set to the pinned NCXchange checkout (its `machines/` folder);
  otherwise it is skipped with a message.

## Invariants that must never break

- REQ-NCX-008, DEC-NCX-002: numbers are printed from exact integer counts of 10^-6, half away
  from zero on the exact value. Never `np.round` (half to even), `floor(x·10^6 + 0.5)` (rounds
  twice) or `repr`/`format` (exponents). The oracle is `exact_text` in
  `tests/support/ncx_programs.py`.
- REQ-NCX-010: every value reaching `to_steps` is finite and below 10^9; `printed` in `_moves.py`
  masks the others to 0 and reports them. A new printed column goes through `printed`.
- REQ-NCX-012, D-148: `write_ncx` takes no machine data. Controller knowledge belongs to
  NCXchange (`.claude/rules/ncx.md`).
- REQ-NCX-017: errors in the order program, then each operation by requirement ID, then by move;
  `operation_errors` in `_refusals.py` lists them in that order.

## Known pitfalls

- The canonical layout `ncx format --check` wants is not known at the f74559c pin (RR-006); only
  the real-`ncx` test checks it, and `SPINDLE=OFF` (DEC-NCX-008) with it. CI has no job that
  builds `ncx` yet (AQ-025), so the test is skipped there too.
- `np.strings` arrays have a fixed width: assigning a longer string into an element truncates it
  silently. Build a new array with `+` or `np.where`, never assign into one.
- The fake `ncx` (`tests/support/ncx_fake.py`) is the real Python interpreter run on a folder per
  step. A venv's `python` on Windows is a launcher with a child; killing it leaves the child
  holding the pipes, so the fake uses `sys._base_executable`.
- `ruff format` on this folder also formats the SPEC's Python block; format only `*.py`.
- REQ-NCX-026's 0.001 mm (`_MIN_ARC_CHORD_MM`, DEC-NCX-016) is the shipped mills' step, not a
  tolerance: it goes when NCXchange checks arcs at the machine's step (D363), not when tol
  changes. A test arc for another rule needs a chord of 0.001 mm or more, or it is refused too.
- `write_ncx` refuses an axial offset a ≠ 0 (REQ-NCX-013, DEC-NCX-018). A test of the Z shift
  (REQ-NCX-007) checks `move_blocks`; one that reaches 10^9 through a also gets that refusal.
- Every `ncx` step fails on a WARNING or an unread stderr line (REQ-NCX-027); only `compile`'s
  `CMP020` is accepted. A fake `ncx` step meant to pass prints no warning.
