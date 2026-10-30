# Decisions: ncx

<!-- The permanent record of why this module is built the way it is. Rules: docs/dev/05, "Module decision records".
     - Write the entry in the same commit as the change that makes the decision, not at the end and not on request.
     - Newest last. IDs DEC-NCX-NNN are never reused.
     - After merge, only the Status line of an entry changes. A changed decision is a new entry that supersedes the old one.
     - Code that follows a decision a reader would not expect cites its ID in a comment. -->

## DEC-NCX-001: The writer returns text; `job` writes the file and owns the folders

- Date: 2026-10-27; decided by: ours (SPEC draft, plan 0007 step 6)
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-010 item 6)
- Decision: `write_ncx` is a pure function from the record to the NCX text and its sections. `run_ncx` starts the `ncx` process on absolute paths the caller gives; it writes no file itself, but `ncx compile` writes the controller files into the staging folder the caller made. `job` writes the NCX file, makes the working and staging folders, and moves the compiled files to the user only after a clean run.
- Why: docs/dev/03, rule 5: files are read and written only in `io`, `job` and `apps`; running the pinned binary is `ncx`'s by `architecture/modules.yaml`. The files `compile` writes are the one exception, on `job`'s folder; AQ-010 item 6 asks Peter to confirm it. A pure writer is testable without a file system.
- Rejected: `write_ncx` writing the file; the text on `ncx`'s stdin (research 27 names file arguments only).
- Where: REQ-NCX-001 to 018; `src/splintercam/job/SPEC.md`, REQ-JOB-016 to 019.

## DEC-NCX-002: The number printer: exact half away from zero, as integer steps in NumPy

- Date: 2026-10-27; decided by: ours (revised after the spec review the same day)
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-010)
- Decision: each column is turned into int64 counts of the step 10^-6 by rounding the exact product x·10^6 half away from zero: Dekker's error-free product gives x·10^6 as p + e exactly (p the rounded product, e its error, both doubles; 10^6 is exact), and the count is decided from floor(p), the exact fraction p − floor(p) and e, ties going away from zero. The text is the count's integer and fractional digits, built with NumPy string operations, trailing zeros trimmed to one decimal; −0 is the count 0. Values of 10^9 or more are refused (REQ-NCX-010), so every count lies below 2^52, where floor, the fraction and the cast to int64 are exact. Feeds and speeds use the same step.
- Why: the split rule puts loops over points into NumPy or a kernel, and research 26's `format_float_positional` is a per-value Python call. `floor(|x|·10^6 + 0.5)` rounds twice: the double nearest 5·10^-7 printed `0.000001` instead of `0.0` (spec review). With the exact product the printed decimal is exactly the rounded value, research 26's rule, and only IEEE addition, subtraction, multiplication and floor decide, the same on every platform (D-055). D-149 fixes the resolution for lengths and angles only; feeds and speeds at the same step keep one printer, far finer than any machine's decimals (ours).
- Rejected: `format_float_positional` per value (a Python loop over every coordinate); Python's `decimal` (a loop too); `floor(x·10^6 + 0.5)` (double rounding above); `np.round` (half to even).
- Where: REQ-NCX-008 to 010.

## DEC-NCX-003: No `ROUND_LIMIT` word in the slice

- Date: 2026-10-27; decided by: ours, provisional on Peter's answer (AQ-010 item 1)
- Status: Accepted 2026-10-27 (AQ-010 item 1); the word comes with the pin that has NCXchange's D363 (RR-006 item 2 asks what f74559c says about it, which does not change this)
- Decision: the writer computes every operation's rounding allowance, the reserve share of its tolerance set (0.1·tol, D-149, REQ-FND-009), and holds it in `NcxSection.round_limit_mm`, but writes no `ROUND_LIMIT`. Writing it comes with the pin that includes NCXchange's D363 (Later).
- Why: Peter answered D363 on 2026-10-02 (the CAM writes `ROUND_LIMIT` per operation; `src/splintercam/foundation/SPEC.md`, Tolerance budget), but research 27 records that f74559c has not implemented D363 (Checked condition 3), and an unknown word most likely fails `check` (not tried: no `ncx` in this run; RR-006 asks). The writer has no input that says what the pin is, so the switch is a code change with the pin, not a condition.
- Rejected: writing it now; the allowance in a `COMMENT` (NCXchange cannot read it).
- Where: REQ-NCX-009.

## DEC-NCX-004: One tool and one speed per program; every axis word; `F` restated per operation

- Date: 2026-10-27; decided by: ours (revised after the CNC review the same day)
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-010 item 4)
- Decision: the program has one tool block, in the first operation; an operation with another tool or speed is refused. Every move but the first carries X, Y and Z. `F` is written where the feed changes and on each operation's first feed move.
- Why: what a second tool block from the clearance height, or a speed block without `TOOL`, compiles to on the three mill files has not been checked (research 26 notes only that Heidenhain takes the speed from `TOOL CALL`); plan 0007 has one tool. Full axis words and `F` per operation let a section be read alone (feature map, section 8: NC code for one operation) and change nothing on the machine, as NCX is modal.
- Rejected: a tool block per operation and a speed-only block (unchecked output); leaving unchanged axes out.
- Where: REQ-NCX-002, 003, 005, 006.

## DEC-NCX-005: `compile` does not run after a failing `format --check` or `check`

- Date: 2026-10-27; decided by: ours
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-010)
- Decision: `format --check` and `check` both run unless the call fails (REQ-NCX-023) or is cancelled; `compile` runs only when both exited 0 without an ERROR.
- Why: a program that fails `check --strict` is not right for the machine, and an NC program compiled anyway could be taken for a good one. `check` after a format difference still shows the machine's view of the words.
- Rejected: always all three; stopping after `format --check`.
- Where: REQ-NCX-019.

## DEC-NCX-006: `CMP020` counted as INFO; other `compile` warnings fail as under `--strict`

- Date: 2026-10-27; decided by: ours, provisional on Peter's answer (AQ-010 item 3)
- Status: Accepted 2026-10-27 (AQ-010 item 3, option (a))
- Decision: `compile` runs without `--strict` (research 27). Its `CMP020`s become one INFO, `NCX_ROUNDED`, per location with their count; any other WARNING keeps its severity and adds `NCX_STRICT_FAILED` (error).
- Why: D-149 makes rounding to the machine's decimals normal and silent (NCXchange D363 retires `CMP020`), and research 27 accepts `CMP020` and nothing else. One message per coordinate would bury real ones, and would be a Python loop over points. Without the added error, a `CMP501` or `CMP022` from `compile` would pass a run that `--strict` would fail (spec and CNC reviews).
- Rejected: `CMP020` as WARNING (every run fails the CLI's `--strict`); dropping it (never swallow).
- Where: REQ-NCX-022.

## DEC-NCX-007: The subprocess: argument list, drained pipes, no timeout, cancel by polling

- Date: 2026-10-27; decided by: ours, the clock exception provisional on AQ-010 item 6
- Status: Accepted 2026-10-27 (AQ-010 item 6: the clock exception confirmed); the reader threads and the one regular expression over the whole text superseded by DEC-NCX-013
- Decision: each step is started with an argument list, no shell, in `call.work_dir`, with the parent's environment. stdout and stderr are read to their end while the process runs (reader threads), decoded as UTF-8 with replacement; stderr is parsed with one compiled regular expression over the whole text; stdout goes to `ctx.logger` at debug level, and for `format --check` into `NCX_STEP_FAILED`'s message. There is no timeout; the wait polls `ctx.cancel` at a fixed interval, a named constant citing this entry, and stops the process when it is set.
- Why: a full pipe blocks the child (one `CMP020` per coordinate is a lot of text). No shell means no quoting. Research 27 gives no run time, and a made-up timeout could kill a slow, correct run; cancellation covers a hung one. The poll interval reads the clock, which docs/dev/03, rule 5 keeps out of layers below 6; waiting on a subprocess cannot avoid it, so AQ-010 item 6 asks Peter to confirm the exception.
- Rejected: `shell=True`; `wait()` with unread pipes; a fixed timeout.
- Where: REQ-NCX-018, 020, 023, 024.

## DEC-NCX-008: `COOLANT=OFF` and `SPINDLE=OFF` before the program end

- Date: 2026-10-27; decided by: ours (CNC review), provisional on AQ-010 item 2 and RR-006
- Status: Accepted 2026-10-27 in substance (AQ-010 item 2: spindle and coolant off before the program end); the form `SPINDLE=OFF` stays provisional until RR-006 (item 3) confirms it is valid NCX at the pin, or the real-`ncx` integration test does
- Decision: after the last operation's last move (a RAPID at or above the clearance height, REQ-CL-012) the writer writes `COOLANT=OFF` and `SPINDLE=OFF`, then `PROGRAM=END`.
- Why: research 26's mapping has no spindle or coolant off, and nothing in the research says what `PROGRAM=END` compiles to or whether the program end stops the spindle on the iTNC 530; relying on it would be guessing controller behaviour. Stopping both explicitly is the state an operator expects when the program ends 5 mm above the part. `COOLANT=OFF` follows the machine file's `[coolant]` ON/OFF codes (research 27); `SPINDLE=OFF` is not confirmed as an NCX value (RR-006): the real-`ncx` integration test checks it, and if it fails the form comes from RR-006's answer.
- Rejected: no stop (the control's end decides; unverified).
- Where: REQ-NCX-001.

## DEC-NCX-009: Note lines in printable ASCII without brackets or backslash

- Date: 2026-10-27; decided by: ours (spec review), from research 27, trap 15
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-010)
- Decision: the writer refuses a note line with a character outside printable ASCII, or with `(`, `)` or `\`. The text is ASCII.
- Why: research 27, trap 15: a bracket inside a Fanuc comment ends it early and the rest of the line runs as code, with no message from `ncx`; the CAM refuses brackets until NCXchange escapes them (R1-14). `\` is NCX's escape character. `cl` already refuses `"` and control characters (REQ-CL-017) but lets umlauts through (DEC-CL-005); the slice's note is empty (AQ-008 (b)), so ASCII only costs nothing now and keeps the NCX file's encoding out of question.
- Rejected: transliterating in the writer (NCXchange's job in comments, research 27); escaping `\` (no note needs it).
- Where: REQ-NCX-015.

## DEC-NCX-010: The operation's name only in `SECTION`, not also as a `COMMENT`

- Date: 2026-10-27; decided by: ours (left to `ncx` by `src/splintercam/cl/SPEC.md`, Scope)
- Status: Accepted 2026-10-27 (SPEC Reviewed, AQ-010)
- Decision: the name is written once, in `SECTION="<name>"`; note lines follow as `COMMENT`.
- Why: the three compilers write `SECTION` as a comment line on every control (research 27, trap 15: Heidenhain `* - …`, Siemens `; …`, Fanuc `( … )`), so the operator sees the name; a second copy adds a line and nothing else.
- Rejected: `COMMENT="<name>"` after `SECTION`.
- Where: REQ-NCX-002.

## DEC-NCX-011: A section ends at its operation's last move

- Date: 2026-10-27; decided by: ours (implementation, plan 0007 step 6)
- Status: Accepted 2026-10-27; confirmed by Peter (AQ-027 item 1), the SPEC's `last_line` comment changed to match
- Decision: `NcxSection.last_line` is the line of the operation's last move. For every section but the last that is the line before the next `SECTION`; for the last, the program end is read as the closing blocks `COOLANT=OFF`, `SPINDLE=OFF`, `PROGRAM=END`, `FILE=END`, so a message on them has the location `program`.
- Why: REQ-NCX-001 writes the spindle and coolant stop after the operations, not in one, and a message about the program's end blocks (an unknown `SPINDLE=OFF`, RR-006) is not an operation's fault. REQ-NCX-021's `program` location exists for such lines.
- Rejected: the last section running to the line before `PROGRAM=END` (it would take the program's closing blocks into the last operation).
- Where: REQ-NCX-002, 021; `src/splintercam/ncx/_write.py`.

## DEC-NCX-012: A tol the tolerance set refuses is reported, not swallowed

- Date: 2026-10-27; decided by: ours (implementation)
- Status: Accepted 2026-10-27; confirmed by Peter (AQ-027 item 2), in the SPEC's failure table and REQ-NCX-017
- Decision: when `ToleranceSet.for_operation(tol)` has no value for an operation's tol (below 2/875 mm or above 1 mm, REQ-FND-010), `write_ncx` returns no program and reports foundation's diagnostic (`TOL_BELOW_MINIMUM`, `TOL_ABOVE_MAXIMUM`) with the operation as its location, after the operation's other errors.
- Why: `cl` accepts any positive tol (REQ-CL-017), and REQ-NCX-009 needs the reserve share of the operation's tolerance set. A tol without a set has no rounding allowance; no requirement names the case, and errors are never swallowed. In plan 0007 `model` checks tol first, so the case does not occur.
- Rejected: `0.1·tol` computed directly (a second copy of REQ-FND-009's share); raising `ValueError` (the record itself is valid).
- Where: REQ-NCX-009, 017; `src/splintercam/ncx/_write.py`.

## DEC-NCX-013: The pipes are drained by `Popen.communicate` with a timeout; stderr is read line by line

- Date: 2026-10-27; decided by: ours (implementation of DEC-NCX-007)
- Status: Accepted 2026-10-27; supersedes DEC-NCX-007 in part (its reader threads, and its one regular expression over the whole text)
- Decision: each step waits in `Popen.communicate(timeout=…)` at the poll interval of DEC-NCX-007, decoding UTF-8 with replacement, and looks at `ctx.cancel` after each timeout; when it is set, the process is killed and its pipes read to the end. No reader threads of our own. stderr is read line by line, each line matched with one compiled regular expression, so a line in no known form is found and kept (REQ-NCX-020); a line of only spaces is dropped.
- Why: `communicate` reads both pipes to their end while it waits (threads on Windows, a selector elsewhere), and the Python documentation guarantees that a timeout loses no output and the call may be repeated. DEC-NCX-007's reader threads are what it does inside; writing them again adds code and nothing else. The test `test_a_long_output_does_not_block` prints 10^5 lines on each pipe.
- Rejected: our own reader threads (the same, longer); `wait()` with unread pipes (blocks on a full pipe); one `finditer` over the whole text (it skips what does not match, and the unread lines must be kept). The line loop is over `ncx`'s messages, not over points; 10^5 lines take well under a second.
- Where: REQ-NCX-018, 024; `src/splintercam/ncx/_run.py`.

## DEC-NCX-014: Readings of the message rules: one `NCX_STRICT_FAILED`, a speed names no move, compile fails closed

- Date: 2026-10-27; decided by: ours (readings of REQ-NCX-010, 020 to 022 and 025; (d) to (f) after the CNC review the same day)
- Status: Accepted 2026-10-27; (e) extended to `format --check` and `check` by DEC-NCX-017 (2026-10-30), so a `CMP020` WARNING kept by (c) now also fails those steps; (f) narrowed to the NCX file by DEC-NCX-019
- Decision: (a) `compile`'s warnings other than `CMP020` keep their place; one `NCX_STRICT_FAILED` follows the step's messages, whatever their number. (b) REQ-NCX-010 names the move for a coordinate or a feed, one diagnostic per move; a spindle speed of 10^9 or more belongs to the operation, not to a move, and its message names the speed. (c) A `CMP020` from `format` or `check` is kept as `ncx` reports it; only `compile`'s are counted. (d) The NCX file is recognised by its resolved path, so a message naming it relatively or through `..` still finds its operation. (e) An unread line from `compile` (REQ-NCX-020's `NCX_OUTPUT_UNREAD`) counts as one of its warnings and adds `NCX_STRICT_FAILED`. (f) Only a `CMP020` of severity WARNING is counted as `NCX_ROUNDED`; one at another severity stays as `ncx` reports it.
- Why: (a) REQ-NCX-025 orders `ncx`'s own messages as printed; the added error is the step's verdict, and one is enough to fail the run. (b) The speed is a header value, written in the tool block. (c) REQ-NCX-022 counts the `CMP020`s of `compile`; `check` does not round (research 26, Checked condition 3), so one from `check` would be news. (d) `ncx`'s path form has not been seen (AQ-025); an exact comparison would lose the operation on `/var` against `/private/var` on macOS. (e) and (f) fail closed (CNC review): `compile` runs without `--strict`, so a warning in a form the parser does not know (a column number, another case, a wrapped line; the form is unchecked at the pin, AQ-025) would otherwise pass as a WARNING, and a `CMP020` raised to ERROR by a later pin would pass as an INFO count. REQ-NCX-022 fails `compile`'s warnings other than `CMP020`; an unread line may be one.
- Rejected: one `NCX_STRICT_FAILED` per warning (repeats the same verdict).
- Where: REQ-NCX-010, 022, 025; `src/splintercam/ncx/_refusals.py`, `src/splintercam/ncx/_messages.py`.

## DEC-NCX-015: Preconditions of `run_ncx`; a value not finite is out of range; a cancel during the last step counts

- Date: 2026-10-27; decided by: ours (spec review the same day)
- Status: Accepted 2026-10-27
- Decision: (a) `run_ncx` raises `ValueError` naming the fields of `call` whose path is not absolute, before any step (REQ-NCX-018 says every path is absolute; a relative `ncx_file` would be read by `ncx` against `work_dir`, another file than `job` wrote). (b) A value that is written (X and Y but on move 0, Z, the centre of an arc, the feed of a LINE or ARC) and is not finite is reported as `NCX_VALUE_OUT_OF_RANGE` with the values of 10^9 or more: `cl` checks z and a apart, and z + a can overflow to infinity, which would otherwise print as `0.0`. (c) When `ctx.cancel` is set while the last step runs and that step ends before the next poll, `run_ncx` returns `CANCELLED`, not its steps. (d) A relative file name in `ncx`'s messages is taken against `call.work_dir`, where `ncx` runs.
- Why: preconditions are programming errors, `ValueError` as in `cl` (DEC-CL-002); a silent wrong coordinate is never acceptable; REQ-NCX-024 says a token set while a step runs ends in `CANCELLED`.
- Rejected: a diagnostic for a relative path (it is the caller's bug, not an outcome); leaving overflow to `cl` (`cl` has no a + z rule).
- Where: REQ-NCX-010, 018, 021, 024; `src/splintercam/ncx/_run.py`, `_moves.py`, `_messages.py`.

## DEC-NCX-016: Arcs whose chord is below 0.001 mm are refused

- Date: 2026-10-27; decided by: Peter (AQ-026 item 1)
- Status: Accepted 2026-10-27; to be replaced by NCXchange's check at the machine's step once its D363 is at the pin (T-039)
- Decision: `write_ncx` refuses every ARC with |sweep| below 2π whose chord, the distance in XY from the previous move's end to its end in the record's values, is below `_MIN_ARC_CHORD_MM` = 0.001 mm, as `NCX_ARC_CHORD_TOO_SHORT` naming the operation and the move (REQ-NCX-026). Full circles are exempt; their end is their start by REQ-CL-014. An arc that also prints degenerate gets both errors, REQ-NCX-016's first.
- Why: NCXchange rounds both ends to the machine's step, 0.001 mm on the three shipped mills (research 27, `[format]` decimals 3); an arc shorter than that can end on its start after rounding, and a control reads end = start as a full circle, a 360° pass through the part. D-149 gives the consistency to NCXchange, but D363 is not implemented at f74559c. The constant is the coarsest step of the shipped files, not the machine's own, which D-148 keeps out of `ncx`. The chord is measured on the record, before the writer's rounding, so the rule does not depend on REQ-NCX-016's.
- Rejected: leaving it to NCXchange alone (unchecked at the pin, AQ-026 option (a)); reading the step from the machine file (D-148).
- Where: REQ-NCX-026; `src/splintercam/ncx/_refusals.py`.

## DEC-NCX-017: `format --check` and `check` fail closed on a WARNING or an unread line

- Date: 2026-10-30; decided by: Peter (AQ-036 item 4, answered 2026-10-27); the readings (a) to (c) ours
- Status: Accepted 2026-10-30
- Decision: in `format --check` and `check`, as in `compile` (DEC-NCX-014 (e)), any WARNING and any `NCX_OUTPUT_UNREAD` line adds one `NCX_STRICT_FAILED` (error) naming the step after the step's messages. (a) Whatever the exit code: with exit 1 the run also gets `NCX_STEP_FAILED`, with another code `NCX_CALL_FAILED`. (b) A `CMP020` WARNING from these two steps fails too; it is still kept as `ncx` reports it (DEC-NCX-014 (c)). (c) The message names the step and, for `compile` only, the accepted `CMP020`; for `format --check` and `check` it says "it fails closed", since `format --check` runs without `--strict`. (d) `NCX_STRICT_FAILED` comes after `ncx`'s messages of the step and before its `NCX_STEP_FAILED` or `NCX_CALL_FAILED`.
- Why: for `check`, research 27, Exit codes: under `--strict` a WARNING exits 1, so exit 0 with one, or a line in no known form, is `ncx` behaving in a way nobody has checked. For `format --check`, exit 0 with a WARNING is documented (0 means no ERROR), and it fails by Peter's choice. In both steps, the stderr form is unchecked at the pin (AQ-025: the stderr form is unchecked at the pin); the program must not reach the machine on it. `NCX_STRICT_FAILED` is an ERROR, so REQ-NCX-019 already keeps `compile` from running. (a) One rule for every step is simpler to read and to test than one that depends on the exit code, and the extra error repeats nothing the operator must act on differently. (b) `check` does not round (research 26, Checked condition 3), so a `CMP020` there is news, not the accepted rounding.
- Rejected: adding the error only when the exit code is 0 (two rules for one verdict); a separate code per step (the location names the step).
- Where: REQ-NCX-027; `src/splintercam/ncx/_messages.py`.

## DEC-NCX-018: An axial offset a ≠ 0 is refused, by its own code, compared exactly; the shift stays

- Date: 2026-10-30; decided by: Peter (AQ-035, answered 2026-10-27: refuse a ≠ 0 as k ≠ 1 is refused); the readings (a) to (c) ours
- Status: Accepted 2026-10-30; goes when a setup sheet states the point or D-155's point words exist (R1-11)
- Decision: `write_ncx` refuses an operation whose axial offset a is not 0 with `NCX_POINT_OFFSET_UNSUPPORTED` (error) naming the operation, k and a. (a) Its own code, not `NCX_POINT_UNSUPPORTED`: the cause and the fix differ (another point against an offset of point 1), and both may come for one operation, k's first, under REQ-NCX-013. (b) Compared exactly with 0, as every comparison in the writer but REQ-NCX-026 (SPEC, Tolerance budget): the smallest positive a still moves every Z, and `cl` takes a ≥ 0 only (REQ-CL-017). (c) REQ-NCX-007's shift is kept in `_moves.printed` and tested on the move blocks, so removing the refusal later is the one change.
- Why: the tool block is `TOOL=n OFFSET:LEN=n` without the point (research 26, trap 3), so with a ≠ 0 every Z is output a above the tip and nothing in the program says so; a wrong length in the register cuts a wrong part with no message (AQ-035, note 7; `src/splintercam/model/SPEC.md`, REQ-MDL-006). The slice has no setup sheet (AQ-035 (a)).
- Rejected: a warning (Peter chose the refusal); removing the shift (it comes back with the setup sheet or the point words, and its tests would go with it).
- Where: REQ-NCX-007, 013; `src/splintercam/ncx/_refusals.py`; the tests changed with it are listed in the progress-log entry `docs/plans/active/0007-log/2026-10-30-ncx-fail-closed-and-point-a.md`.

## DEC-NCX-019: Only `compile`'s `CMP020` on the NCX file is the accepted rounding

- Date: 2026-10-30; decided by: ours (CNC review of DEC-NCX-017)
- Status: Accepted 2026-10-30
- Decision: a `CMP020` WARNING of `compile` is counted as `NCX_ROUNDED` only when its file is `call.ncx_file` (DEC-NCX-014 (d)); one naming the machine file or another input is kept as `ncx` reports it and fails the step with `NCX_STRICT_FAILED`, as any other `compile` warning.
- Why: D-149 accepts the rounding of our program's values to the machine's decimals, which is what research 26 (Checked condition 3) describes `CMP020` as. A `CMP020` on another file is not that rounding, so it is news, the reasoning of DEC-NCX-017 (b); counting it would hide it as an INFO at `ncx compile`. Fail closed, as DEC-NCX-014 (e) and (f).
- Rejected: counting every `CMP020` of `compile` (the reading before; it accepted a warning nobody has seen).
- Where: REQ-NCX-022; `src/splintercam/ncx/_messages.py`.
