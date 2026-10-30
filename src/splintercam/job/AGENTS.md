# AGENTS.md: job

Layer 5. Runs one job from its JSON file to the NC program: the job file (stage 1), the output
folder, `model.check_job`, `io.read_dxf_contour`, each operation's strategy, `cl.make_cl_data`,
`ncx.write_ncx`, the NCX file, and `ncx.run_ncx` in a temporary folder with the compiled files
moved only after a clean run. Contract: `./SPEC.md`. Why it is built this way: `./DECISIONS.md`
(read it before changing behaviour). Public API: `./__init__.py` (`run_job`, `JobReport`,
`default_context`, `Diagnostic`, `Severity`). No C++ part. The only interface `apps` use.

## Files

- `_json.py`: reading the file (UTF-8, BOM, repeated keys kept, no NaN or infinities).
- `_layout.py`: the layout of version 1 as data, the depth-first key walk, the values `job`
  checks, the paths and `ncx` lookup, and `model`'s types built with the values as read.
- `_registry.py`: the strategy registry and the location rewrite of REQ-JOB-014.
- `_output.py`: stages 2, 8 and 9 (folders, the NCX file, `ncx`, the move).
- `_run.py`: the stages in order, the stop and cancel rules, `JobReport`.
- `_context.py`: `default_context`.

## Commands

- `uv run pytest tests/job` (or `tools/test-one job`).
- The golden case's `ncx` test needs `ncx` on the path and `SPLINTERCAM_NCXCHANGE` set to the
  pinned NCXchange checkout; otherwise it is skipped with a message.

## Invariants that must never break

- Nothing is written into the output folder before stage 8; an output folder that is not new or
  empty is refused and left as it is (REQ-JOB-010, DEC-JOB-005).
- A report with an ERROR or `CANCELLED` has `nc_files == ()`; compiled files reach the output
  folder only after a clean `run_ncx` (REQ-JOB-019, DEC-JOB-008, 011).
- Stage 1's diagnostics come in the layout's key order, unknown and repeated keys after their
  object's keys by code point, then `JOB_MACHINE_OVERRIDDEN`, `JOB_INPUTS` last (REQ-JOB-020).
  A new key goes into `_LAYOUT` in its place; a value `job` checks itself goes into `_checks`.
- `job` passes values to `model` as read; it never checks a type `model` checks (DEC-JOB-003).

## Known pitfalls

- `ruff format` on this folder also formats the SPEC's Python block; format only `*.py`.
- Python's `json` keeps the last of a repeated key and reads `NaN`; `_json.py`'s hooks are what
  make both errors. `json` raises a plain `ValueError` (not `JSONDecodeError`) for an int over its
  digit limit; it is caught with the hooks' error.
- The tests replace `splintercam.job._output.run_ncx` and `splintercam.job._run.REGISTRY`; an
  import of either name elsewhere is not replaced (DEC-JOB-012).
- `job` never recurses over values: `depth` in `_json.py` refuses nesting beyond `_MAX_DEPTH`
  first (DEC-JOB-009 (7)); a new layout level raises it by itself.
- A stage that returns no value must report an ERROR or `CANCELLED`; `_Run.take` raises
  `ValueError` otherwise (a producer's bug).
- macOS file systems ignore case: two test files `B.h` and `b.h` are one file.
- `tests/support/job_files.py` loads the golden case's `make_part.py` with bytecode writing off,
  so no `__pycache__` appears in `testdata/`.
