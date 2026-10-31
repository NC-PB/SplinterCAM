# 2026-10-31, step 7 (`job`: lane H's second-review fixes merged with lane I's `strict`)

- Pull request 91 was merged at `537852c` before lane H's last two commits reached it; the Project Spike session cherry-picked them onto `job/review2-0007-step7` (pull request 94). Pull request 93 (`apps/cli`, lane I) then merged into `main` with its own changes to `src/splintercam/job/` (AQ-040 (b): `strict` in `run_job`, `_after_ncx`, `_clean_up`, `_withheld`, DEC-JOB-016, REQ-JOB-001 and 019 amended).
- `main` merged into `job/review2-0007-step7`. Conflicts:
  - `src/splintercam/job/_output.py`: both kept. `_roll_back` now names the files it could not remove by absolute path (lane I's form), for a failed move and for a cancel during the move alike; `_within` (the `samefile` check before `mkdtemp`) stays; lane I's `_after_ncx` hands `ctx` to `_move`, so a cancel during the move still rolls back; lane I's `compile_ncx(read, …)`, `_withheld` and `_clean_up` unchanged.
  - `src/splintercam/job/SPEC.md`: REQ-JOB-001 and 019 carry lane I's `strict` sentences; every "Verified by" cell holds both lanes' tests; the size note gives the merged NLOC.
- Run: `uv run pytest tests/job tests/apps` 200 passed, 3 skipped (the real `ncx` and the end-to-end run, not on this Mac); `tools/lint` and `tools/arch-check` pass; `tools/size-check` passes and reports `job` at 518 NLOC of 500: AQ-039, not blocking.
- Open: AQ-039.
