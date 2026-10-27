# Decisions: job

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-JOB-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-JOB-001: `run_job` returns a report, not a `Result`

- Date: 2026-10-27; decided by: ours (SPEC draft, plan 0007 step 7)
- Status: Provisional (SPEC Draft, AQ-011)
- Decision: `run_job` returns a `JobReport` with the diagnostics, the record, the NCX file and the NC files, and an `ok` property: no ERROR and no `CANCELLED`.
- Why: a run that fails in `ncx` has still written the NCX file, which the user needs to see (feature map, section 8: output with errors is still written, clearly marked). REQ-FND-004's `Result` carries a value only when it is `ok`. `CANCELLED` is a warning (REQ-FND-013), but a cancelled run has no program, so it is not `ok` (spec review).
- Rejected: `Result[JobReport]` (no value exactly when the files matter most); raising (expected outcomes are diagnostics).
- Where: REQ-JOB-001, 016 to 019.

## DEC-JOB-002: Stage order, stop after a failing stage, every operation planned

- Date: 2026-10-27; decided by: ours
- Status: Provisional (SPEC Draft, AQ-011)
- Decision: the nine stages of REQ-JOB-001 run in order; the first stage with an error ends the run. The output folder is checked second, before any computation. Within stage 5 every operation is planned before the run stops, so the user sees every operation's errors at once. No NCX is written when any operation failed.
- Why: a later stage needs the earlier one's value; checking the folder early saves a run that cannot be written. A program with one operation missing would machine a different part than the job describes; the slice writes all or nothing before `ncx`.
- Rejected: an NCX of the operations that planned (a part silently incomplete); stopping at the first failing operation (one fix per run).
- Where: REQ-JOB-001, 010, 014.

## DEC-JOB-003: Job file keys with their unit, values passed to `model` as read

- Date: 2026-10-27; decided by: ours
- Status: Provisional (SPEC Draft, AQ-011)
- Decision: the job file's keys carry their unit (`diameter_mm`, `tol_mm`, `spindle_rpm`), as D-049 asks every value to declare its unit; the job checks only the file's structure (keys, objects, arrays, the format and version, the tool type, the part's unit and paths) and passes every value to `model` as `json` gives it, arrays as tuples. `json` is read with a pairs hook, so repeated keys are seen, a constant hook that refuses `NaN` and the infinities, and a float hook that refuses a number reading as infinite (`1e400`). `parameters` becomes (name, value) pairs in file order with repeats kept. A UTF-8 byte-order mark is accepted (`utf-8-sig`). An optional key given as `null` is the same as absent. The values `model` does not see (format, version, program, paths) are type-checked here, with `bool` refused where an `int` is meant.
- Why: `model`'s `check_job` already checks types, including `true` passing as 1 (REQ-MDL-029); checking them again in `job` would be a second copy of the same rules. Python's `json` keeps the last of a repeated key and reads `NaN`, which is not JSON (RFC 8259), so both need the hooks. Windows Notepad writes a byte-order mark; refusing it would be a confusing error for no gain.
- Rejected: a JSON Schema (`schemas/`; a new dependency for a file of ten keys, ADR needed); keys without units (`diameter`; a unit mistake between mm and inch is the common one, D-028).
- Where: REQ-JOB-002 to 008.

## DEC-JOB-004: Paths relative to the job file; the machine file can be given on the call

- Date: 2026-10-27; decided by: ours, provisional on AQ-011 item 3
- Status: Provisional
- Decision: `part.dxf` and `machine` are resolved against the job file's folder when relative. `run_job`'s `machine_file` overrides `machine`. A missing machine file is an error in stage 1, before any computation, and every run names the machine file and the `ncx` executable it used (`JOB_INPUTS`, info). The tests find the pinned NCXchange checkout, with its `machines/` folder, through the environment variable `SPLINTERCAM_NCXCHANGE`, and are skipped with a message without it.
- Why: a job folder can be moved as a whole. The NCXchange machine files are not in this repository (MIT, and they would need a `NOTICE` entry, and they belong to the pinned NCXchange); CI and the end-to-end test take them from the pinned NCXchange checkout and pass the path. An override that silently changes the machine could compile a program for the wrong machine, so the report names it (spec review).
- Rejected: paths relative to the working directory (a job then runs only from one place); copying NCXchange's machine files into `testdata/` (a licence entry and a copy that drifts from the pin).
- Where: REQ-JOB-009; `src/splintercam/apps/cli/SPEC.md`, REQ-CLI-008.

## DEC-JOB-005: The output folder must be new or empty

- Date: 2026-10-27; decided by: ours, provisional on AQ-011 item 2
- Status: Provisional
- Decision: `run_job` refuses an output folder that exists and holds anything, with `JOB_OUTPUT_NOT_EMPTY`, and deletes nothing in it.
- Why: when `ncx compile` fails it writes no NC program; an NC program from an earlier run left in the folder would look like this run's result and could reach the machine. Refusing is safer than deleting files the CAM did not make.
- Rejected: overwriting files of the same name (the stale-file case above when this run writes none); deleting the folder's content (deletes what a user put there).
- Where: REQ-JOB-010.

## DEC-JOB-006: The strategy registry and the assumed planning function

- Date: 2026-10-27; decided by: ours, provisional on AQ-014 (alignment with `src/splintercam/strategies/profile/SPEC.md`, lane B1)
- Status: Provisional
- Decision: the registry is a fixed mapping in `job` from strategy id to (declarations, planning function). The planning function is assumed to take the checked job's data, the operation's index, the part's loop and a `Context` carrying the operation's tolerance set, and to return a `Result` holding one `cl` operation (`ClOperation` from `make_operation`) or diagnostics.
- Why: docs/dev/03 asks for one uniform strategy interface; the task for this lane fixed only "a function that takes the job's data for one operation and returns a cl operation or diagnostics", so the exact form is named in AQ-014 for the two drafts to agree on.
- Rejected: entry points or a plugin registry (feature map, section 9: later); a registry in `model` (model knows no strategy).
- Where: REQ-JOB-013, 014.

## DEC-JOB-007: The working folder for `ncx` is a new temporary folder

- Date: 2026-10-27; decided by: ours
- Status: Provisional (SPEC Draft, AQ-011)
- Decision: `run_job` creates a new folder with the standard library's temporary-folder function for every run, holding two empty folders side by side: the working folder (`ncx`'s current folder) and the staging folder for `ncx compile`. It passes both to `run_ncx` with every path absolute, and removes the temporary folder, with what it holds, afterwards, also after an error or a cancel; a folder it cannot remove is named in a warning.
- Why: research 27, traps 3 and 4: `ncx` loads every plugin in `plugins/` of its working folder and reads `ncx.toml` there, so it must run in a folder the CAM controls; the user's output folder is not one (the user may put anything there). `ncx` runs with the working folder as its current folder, so a relative path would resolve there (spec review).
- Rejected: the output folder as working folder; the job file's folder.
- Where: REQ-JOB-018.

## DEC-JOB-008: Compiled files reach the output folder only after a clean `ncx` run

- Date: 2026-10-27; decided by: ours (spec and CNC reviews)
- Status: Provisional (SPEC Draft, AQ-011 item 1)
- Decision: `ncx compile` writes into the staging folder; `run_job` moves its files into the output folder only when `run_ncx` is `ok` (every step exited 0, no ERROR, no `compile` warning but `CMP020`, not cancelled). Otherwise the output folder holds the NCX file alone.
- Why: research 27, test 5: a program with an error gives no NC file. Without staging, a `compile` killed by a cancel or a crash could leave half a program in the output folder, and a program `compile` warned about (but did not refuse without `--strict`) would look like a good one; either could reach the machine.
- Rejected: compiling into the output folder and deleting on failure (a crash of the CAM itself leaves the file); marking failed files by name (an operator copying files to the control does not see the mark).
- Where: REQ-JOB-019; `src/splintercam/ncx/SPEC.md`, REQ-NCX-022.
