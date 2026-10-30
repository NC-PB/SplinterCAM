# Decisions: job

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-JOB-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-JOB-001: `run_job` returns a report, not a `Result`

- Date: 2026-10-27; decided by: ours (SPEC draft, plan 0007 step 7)
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-011)
- Decision: `run_job` returns a `JobReport` with the diagnostics, the record, the NCX file and the NC files, and an `ok` property: no ERROR and no `CANCELLED`.
- Why: a run that fails in `ncx` has still written the NCX file, which the user needs to see (feature map, section 8: output with errors is still written, clearly marked). REQ-FND-004's `Result` carries a value only when it is `ok`. `CANCELLED` is a warning (REQ-FND-013), but a cancelled run has no program, so it is not `ok` (spec review).
- Rejected: `Result[JobReport]` (no value exactly when the files matter most); raising (expected outcomes are diagnostics).
- Where: REQ-JOB-001, 016 to 019.

## DEC-JOB-002: Stage order, stop after a failing stage, every operation planned

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-011)
- Decision: the nine stages of REQ-JOB-001 run in order; the first stage with an error ends the run. The output folder is checked second, before any computation. Within stage 5 every operation is planned before the run stops, so the user sees every operation's errors at once. No NCX is written when any operation failed.
- Why: a later stage needs the earlier one's value; checking the folder early saves a run that cannot be written. A program with one operation missing would machine a different part than the job describes; the slice writes all or nothing before `ncx`.
- Rejected: an NCX of the operations that planned (a part silently incomplete); stopping at the first failing operation (one fix per run).
- Where: REQ-JOB-001, 010, 014.

## DEC-JOB-003: Job file keys with their unit, values passed to `model` as read

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-011)
- Decision: the job file's keys carry their unit (`diameter_mm`, `tol_mm`, `spindle_rpm`), as D-049 asks every value to declare its unit; the job checks only the file's structure (keys, objects, arrays, the format and version, the tool type, the part's unit and paths) and passes every value to `model` as `json` gives it, arrays as tuples. `json` is read with a pairs hook, so repeated keys are seen, a constant hook that refuses `NaN` and the infinities, and a float hook that refuses a number reading as infinite (`1e400`). `parameters` becomes (name, value) pairs in file order with repeats kept. A UTF-8 byte-order mark is accepted (`utf-8-sig`). An optional key given as `null` is the same as absent. The values `model` does not see (format, version, program, paths) are type-checked here, with `bool` refused where an `int` is meant.
- Why: `model`'s `check_job` already checks types, including `true` passing as 1 (REQ-MDL-029); checking them again in `job` would be a second copy of the same rules. Python's `json` keeps the last of a repeated key and reads `NaN`, which is not JSON (RFC 8259), so both need the hooks. Windows Notepad writes a byte-order mark; refusing it would be a confusing error for no gain.
- Rejected: a JSON Schema (`schemas/`; a new dependency for a file of ten keys, ADR needed); keys without units (`diameter`; a unit mistake between mm and inch is the common one, D-028).
- Where: REQ-JOB-002 to 008.

## DEC-JOB-004: Paths relative to the job file; the machine file can be given on the call

- Date: 2026-10-27; decided by: ours, provisional on AQ-011 item 3
- Status: Accepted 2026-10-27 (AQ-011 item 3)
- Decision: `part.dxf` and `machine` are resolved against the job file's folder when relative. `run_job`'s `machine_file` overrides `machine`. A missing machine file is an error in stage 1, before any computation, and every run names the machine file and the `ncx` executable it used (`JOB_INPUTS`, info). The tests find the pinned NCXchange checkout, with its `machines/` folder, through the environment variable `SPLINTERCAM_NCXCHANGE`, and are skipped with a message without it.
- Why: a job folder can be moved as a whole. The NCXchange machine files are not in this repository (MIT, and they would need a `NOTICE` entry, and they belong to the pinned NCXchange); CI and the end-to-end test take them from the pinned NCXchange checkout and pass the path. An override that silently changes the machine could compile a program for the wrong machine, so the report names it (spec review).
- Rejected: paths relative to the working directory (a job then runs only from one place); copying NCXchange's machine files into `testdata/` (a licence entry and a copy that drifts from the pin).
- Where: REQ-JOB-009; `src/splintercam/apps/cli/SPEC.md`, REQ-CLI-008.

## DEC-JOB-005: The output folder must be new or empty

- Date: 2026-10-27; decided by: ours, provisional on AQ-011 item 2
- Status: Accepted 2026-10-27 (AQ-011 item 2)
- Decision: `run_job` refuses an output folder that exists and holds anything, with `JOB_OUTPUT_NOT_EMPTY`, and deletes nothing in it.
- Why: when `ncx compile` fails it writes no NC program; an NC program from an earlier run left in the folder would look like this run's result and could reach the machine. Refusing is safer than deleting files the CAM did not make.
- Rejected: overwriting files of the same name (the stale-file case above when this run writes none); deleting the folder's content (deletes what a user put there).
- Where: REQ-JOB-010.

## DEC-JOB-006: The strategy registry builds each strategy's typed input

- Date: 2026-10-27; decided by: Peter (AQ-014: the typed form of `src/splintercam/strategies/profile/SPEC.md`, the pattern for every strategy); the registry's shape and the location rule ours
- Status: Accepted 2026-10-27 (AQ-014)
- Decision: the registry is a fixed mapping in `job` from strategy id to (declarations, an input builder of `job`'s, the strategy's planning function `plan(task, ctx) -> Result[ClOperation]`). For `profile` the builder makes `ProfileInput(contour, tool, stock, operation)` from the part's loop, the checked job's tool with the operation's T number, the setup's stock and the checked operation; `job` passes `ctx` with only its tolerance set replaced by `ToleranceSet.for_operation` of the operation's tol. A strategy's diagnostic location is rewritten to model's form: a leading `operation (<name>)` (DEC-PRF-005) becomes `operation <index> (<name>)` and the rest is kept; `None` becomes `operation <index> (<name>)`; any other location `<loc>` (offset2d's, passed on by the strategy) becomes `operation <index> (<name>): <loc>`.
- Why: each strategy declares exactly what it needs as a type, so a strategy never reads the whole job and its preconditions can be stated and checked (profile SPEC, Interface); `job` is the one place that knows the job's layout. The location rule gives one form for every operation diagnostic in a report, as `model` writes them (REQ-MDL-027), without the strategy knowing its index.
- Rejected: one signature over the whole job (`plan(job, operation_index, part, ctx)`, this lane's first draft: every strategy would dig its values out of `JobData`); entry points or a plugin registry (feature map, section 9: later); a registry in `model` (model knows no strategy).
- Where: REQ-JOB-013, 014.

## DEC-JOB-007: The working folder for `ncx` is a new temporary folder

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-011)
- Decision: `run_job` creates a new folder with the standard library's temporary-folder function for every run, holding two empty folders side by side: the working folder (`ncx`'s current folder) and the staging folder for `ncx compile`. It passes both to `run_ncx` with every path absolute, and removes the temporary folder, with what it holds, afterwards, also after an error or a cancel; a folder it cannot remove is named in a warning.
- Why: research 27, traps 3 and 4: `ncx` loads every plugin in `plugins/` of its working folder and reads `ncx.toml` there, so it must run in a folder the CAM controls; the user's output folder is not one (the user may put anything there). `ncx` runs with the working folder as its current folder, so a relative path would resolve there (spec review).
- Rejected: the output folder as working folder; the job file's folder.
- Where: REQ-JOB-018.

## DEC-JOB-008: Compiled files reach the output folder only after a clean `ncx` run

- Date: 2026-10-27; decided by: ours (spec and CNC reviews)
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-011 item 1)
- Decision: `ncx compile` writes into the staging folder; `run_job` moves its files into the output folder only when `run_ncx` is `ok` (every step exited 0, no ERROR, no `compile` warning but `CMP020`, not cancelled). Otherwise the output folder holds the NCX file alone.
- Why: research 27, test 5: a program with an error gives no NC file. Without staging, a `compile` killed by a cancel or a crash could leave half a program in the output folder, and a program `compile` warned about (but did not refuse without `--strict`) would look like a good one; either could reach the machine.
- Rejected: compiling into the output folder and deleting on failure (a crash of the CAM itself leaves the file); marking failed files by name (an operator copying files to the control does not see the mark).
- Where: REQ-JOB-019; `src/splintercam/ncx/SPEC.md`, REQ-NCX-022.

## DEC-JOB-009: Stage 1's readings where the SPEC's words leave a choice

- Date: 2026-10-30; decided by: ours (implementation, plan 0007 step 7)
- Status: Accepted 2026-10-30 (box 2, listed in the pull request)
- Decision: (1) `null` for a required object or array is `JOB_KEY_MISSING`, as an absent key, since `null` and absent mean the same for optional keys; a required value given as `null` is passed to `model` (or to `job`'s own check of REQ-JOB-007, 008), which names its type. (2) `JOB_INPUTS` is reported after stage 1's errors too, once the format and version are read, naming `none` for a machine file it could not resolve; it is never reported for `JOB_FILE_*` or `JOB_FORMAT_UNSUPPORTED`. (3) `machine_file` given and the job's `machine` not a non-empty string: `JOB_VALUE_INVALID` at `machine`, the file is still wrong. (4) `JOB_FILE_INVALID` is located `line <L>, column <C>`, 1-based as `json` counts; for `NaN`, an infinity or a number beyond the double range (`1e400`, an int over `json`'s digit limit), which `json` reports without a place, a second pass over the text finds the first such number outside a string. (5) Unknown and repeated keys of one object are one diagnostic per key name, sorted together by name; a name both unknown and repeated is `JOB_KEY_UNKNOWN`; a repeated key gets no other check (so `"part": null, "part": {...}` is `JOB_KEY_REPEATED` alone), and the run stops in stage 1, so none of its values is used. (7) An int beyond the double range (a 400-digit `diameter_mm`) is `JOB_FILE_INVALID` like `1e400`, and a file nested too deeply for Python's `json` (`RecursionError`) is `JOB_FILE_INVALID` at line 1, column 1; so is one nested deeper than the layout holds plus one level (`_MAX_DEPTH`, computed from the layout: 6 for version 1), measured without recursion before any value is walked, since `job`'s and `model`'s own recursion over values would stop at Python's limit of about 1000 frames (spec review, second round). A value one level deeper than the layout (`"diameter_mm": [[1]]`) still reaches `model` and its type error. An int that reads as an infinite double is refused by the same rule in both passes; one that rounds to the largest double reaches `model`, which refuses it as no number. (8) A value `model` refuses is located and named by `model` (REQ-MDL-027): a `null` `tool` reads `tool_number must be an int` at `operation 1 (PROFILE_1)`, `model`'s field name, not the file's key; mapping `model`'s names to the file's keys is left to the job container (spec review, noted). (6) A tool type that is not a string (`null`, `1`) is `JOB_TOOL_TYPE_UNSUPPORTED`, as any other type.
- Why: each keeps one diagnostic per mistake at the key the user must change, and keeps the machine file and `ncx` visible in every report that got past the format (DEC-JOB-004). The second pass reads text `json` has already accepted up to that number, so strings are recognised exactly.
- Rejected: `JOB_STRUCTURE_INVALID` for `null` (the user left it out in effect); no `JOB_INPUTS` after an error (the machine file is what a user checks first when the run fails); a hand-written JSON scanner with positions (more code than the second pass).
- Where: REQ-JOB-002, 004, 005, 007 to 009, 020; `src/splintercam/job/_json.py`, `_layout.py`.

## DEC-JOB-010: Paths made absolute without resolving links

- Date: 2026-10-30; decided by: ours
- Status: Accepted 2026-10-30 (box 2)
- Decision: every path `job` passes on is the given path joined to the current folder (or to the job file's folder) with `.` and `..` taken out (`os.path.normpath` of `Path.absolute()`); links are not resolved.
- Why: REQ-JOB-009 and 018 ask for absolute paths and `JOB_INPUTS` must name the file as the user knows it. `Path.resolve()` would replace a linked `ncx` (a launcher, a version link) by its target, which then runs with another name, and would print a path the user never wrote.
- Limit (spec review): `..` is taken out by text, so for a job file reached through a linked folder (`jobs/current` → `/data/2026/a`) a relative `../machines/m.toml` names `jobs/machines/m.toml`, where the operating system would open `/data/2026/machines/m.toml`. `JOB_INPUTS` names the file used, so the difference is visible; job folders are not expected to be links in the slice.
- Rejected: `Path.resolve()`; `Path.absolute()` alone (keeps `..`, so `JOB_INPUTS` names `out/../jobs/a`).
- Where: `absolute` in `src/splintercam/job/_layout.py`.

## DEC-JOB-011: Stage 9's edges: all or none, cancel wins, a file at the output path

- Date: 2026-10-30; decided by: ours
- Status: Accepted 2026-10-30 (box 2)
- Decision: (1) The compiled files are moved in code-point order; if one move fails, the files already moved are removed again and `JOB_OUTPUT_UNWRITABLE` is reported, so `nc_files` is empty. (2) A cancel seen after `run_ncx` returned clean moves nothing and reports `CANCELLED`; it is polled before each file and after the last, and the files already placed are removed (spec review, second round). (3) A file (not a folder) at the output path is `JOB_OUTPUT_NOT_EMPTY` (it exists and is not an empty folder, REQ-JOB-010's words), and is left as it is.
- Why: DEC-JOB-008 and the SPEC's second invariant: a report with an error or a cancel has no NC file, and no half set of files is left that looks like a program. A cancel is the user's "stop", which no later step overrides.
- Rejected: leaving the files moved before a failure (half a program set); `JOB_OUTPUT_UNWRITABLE` for a file at the path (the file is there, nothing failed to write).
- Where: REQ-JOB-010, 019, 021; `src/splintercam/job/_output.py`.

## DEC-JOB-012: The tests' fake `ncx` replaces `run_ncx` where `job` calls it

- Date: 2026-10-30; decided by: ours
- Status: Accepted 2026-10-30 (box 2)
- Decision: the integration and property tests put a fake `run_ncx` (`tests/support/job_files.py`, `FakeRunNcx`) in place of `splintercam.job._output.run_ncx`; it records the call and what the working and staging folders held, writes files into the staging folder, and returns clean, failed or cancelled. The real process is run by `ncx`'s own tests (`tests/ncx/integration/`) and by the golden case with the real `ncx`.
- Why: `ncx`'s fake (`tests/support/ncx_fake.py`) is the Python interpreter run on a step folder inside the working folder, and REQ-JOB-018 makes that folder new and empty, so the fake's step folders cannot be there; an executable script would need a shebang, which Windows does not run, or a batch file, whose argument quoting differs. What REQ-JOB-017 to 019 and 021 test is `job`'s handling of the call and its outcome, which the in-process fake drives exactly on every platform.
- Rejected: a script with a shebang (not on Windows); a `.cmd` wrapper (argument quoting through `cmd.exe`).
- Where: `tests/job/conftest.py`, `tests/job/integration/`, `tests/job/property/`.

## DEC-JOB-013: Files reach the output folder under a partial name, then are renamed

- Date: 2026-10-30; decided by: ours (cnc review, must-fix M1)
- Status: Accepted 2026-10-30 (box 2)
- Decision: the NCX file and each compiled file are written into the output folder as `.<name>.partial` and then renamed to `<name>` (`Path.replace`, within one folder); the partial file is removed after a failure. A compiled file is copied from the staging folder, not moved. A staging entry that is a folder or a link, or whose name is already in the output folder (the NCX file), stops the move with `JOB_OUTPUT_UNWRITABLE`; files already placed are removed, and any that cannot be removed are named in the message.
- Why: the staging folder is in the system's temporary folder, and the output folder is often another volume (a USB stick or a network share for the control). There a move is a copy and a delete, and a full disk, a pulled stick or a crash half-way would leave a cut-off program under its real name, which looks like a good one. A rename within one folder is atomic, so the real name only ever holds a whole file; a leftover `.partial` file has a name no control program list shows as `.h`.
- Rejected: `shutil.move` (the cnc review's case); the staging folder inside the output folder (DEC-JOB-007: the CAM controls the working folder, not the user's); trusting the control to refuse a program without its end block (not checked against the iTNC 530 manuals).
- Note (spec review, second round): when a partial file cannot be removed after a failure, the first reason is kept and the partial file is named in the message.
- Where: REQ-JOB-016, 019; `_place` and `_move` in `src/splintercam/job/_output.py`.

## DEC-JOB-014: A temporary folder that cannot be made, or lies in the output folder, is an error

- Date: 2026-10-30; decided by: ours (spec review)
- Status: Accepted 2026-10-30 (box 2)
- Decision: when the temporary folder of stage 9 or its two folders cannot be made, or the temporary folder lies inside the output folder (`TMPDIR` or `TEMP` set to it), `run_job` reports `JOB_WORK_DIR_UNWRITABLE` (error) naming the folder and runs no `ncx` step; the NCX file stays written and named. The SPEC's failure table gains the row.
- Why: the `OSError` escaped `run_job` after the NCX file was written, losing the report (expected outcomes are typed diagnostics, AGENTS.md); REQ-JOB-018 says the folder is outside the output folder, which `tempfile` alone does not ensure.
- Rejected: `JOB_OUTPUT_UNWRITABLE` (the output folder is fine; the user would look in the wrong place); a temporary folder beside the output folder (the user's folder, DEC-JOB-007).
- Note (spec review, second round): the check is made on the system's temporary folder before `mkdtemp`, so no stray folder is made in the output folder, and compares with `Path.samefile` up the parents, so a link or a name in another case that reaches the output folder is caught.
- Where: REQ-JOB-018; `compile_ncx` in `src/splintercam/job/_output.py`.

## DEC-JOB-015: A machine file given on the call of another name is a warning

- Date: 2026-10-30; decided by: Peter (AQ-036 2 (b)); the comparison ours
- Status: Accepted 2026-10-30 (AQ-036)
- Decision: when `machine_file` is given and its file name differs from the file name of the job's `machine`, stage 1 reports `JOB_MACHINE_OVERRIDDEN` (warning) at `machine`, naming both, after stage 1's other diagnostics and before `JOB_INPUTS`. The given file is still used and the program still compiled (AQ-036 1 (a): warnings do not withhold the program; `apps/cli --strict` fails on them). The names are compared as strings, case included, without the folders, so the pinned NCXchange checkout's `machines/heidenhain-itnc530.toml` given for a job naming `heidenhain-itnc530.toml` is no warning. Nothing is reported when the job's `machine` is not a non-empty string (that is `JOB_VALUE_INVALID` already).
- Why: an override that compiles for another control than the job names showed only as INFO in `JOB_INPUTS` (cnc review S2); a warning is seen and counts under `--strict`. The folder is expected to differ (DEC-JOB-004: the machine files come from the checkout), the name is what tells the control.
- Rejected: comparing full paths (every CI and end-to-end run would warn); comparing file contents (a copy of the same file in another folder is fine, but reading TOML is `ncx`'s); case-insensitive names (on a file system that ignores case the same file under another case is rare, and a warning there costs nothing).
- Limit (spec review, second round): the file name is taken by `pathlib` of the platform, so a job `machine` written with backslashes (`machines\\heidenhain-itnc530.toml`) is one name on POSIX and warns there, but not on Windows. Job files in the slice name the machine without a folder.
- Where: REQ-JOB-009, 020; `_overridden` in `src/splintercam/job/_layout.py`. Supersedes in part DEC-JOB-004 ("every run names the machine file": still true; the override now also warns).
