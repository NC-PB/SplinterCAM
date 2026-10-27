# 2026-10-27, step 6 (`ncx`: Peter's answers to AQ-025 to AQ-028)

- Branch `ncx/impl-0007-step6`, pull request 87, headless run (lane F). Peter answered AQ-025 to AQ-028 the same day.
- AQ-026 item 1: guard in `ncx` as well. New REQ-NCX-026 in `src/splintercam/ncx/SPEC.md`: an ARC with |sweep| below 2π whose chord in XY is below 0.001 mm is refused as `NCX_ARC_CHORD_TOO_SHORT`, naming the operation and the move (DEC-NCX-016; `_MIN_ARC_CHORD_MM` in `src/splintercam/ncx/_refusals.py`, a constant until NCXchange D363). Items 2 and 3 as recommended: no change.
- AQ-027, all three as proposed: `NcxSection.last_line`'s SPEC comment is now "1-based line of its last move" (DEC-NCX-011 confirmed); the failure table lists `TOL_BELOW_MINIMUM` and `TOL_ABOVE_MAXIMUM`, and REQ-NCX-017 puts the operation's tol last (DEC-NCX-012 confirmed); REQ-NCX-014 refuses COM0 and LPT0.
- AQ-028: the label `large-change` is on pull request 87; no split. AQ-025: the CI step that builds the pinned `ncx` is the Project Spike session's pull request 88, not merged yet, so the real-`ncx` test still skips in this pull request's CI.
- Tests first in `tests/ncx/unit/test_refusals.py`: chords of 0.0009 mm refused and 0.0011 mm written in both directions, a full circle written, REQ-NCX-016's arcs now also refused by 026 (016 first), the order 013, 016, 026, then the tol in one operation; COM0 and lpt0 refused. Seven failed for the expected reason before the code; 104 pass and 6 skip after it.
- Local checks (rule 10): `uv run pytest tests/ncx`, ruff and pyright on `src/splintercam/ncx` and `tests/ncx` (clean), `tools/arch-check`, `tools/size-check`.
- Open: none of AQ-025 to AQ-028. DEC-NCX-008 (`SPINDLE=OFF`) stays provisional until the real-`ncx` test runs with pull request 88.
